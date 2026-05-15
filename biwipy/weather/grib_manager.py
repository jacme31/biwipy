#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 23 13:00:05 2025

@author: jacme
Gribmg : module to read grib files and interpolate wind data
- read grib files (0.25 deg) with pygrib
- build a wind representation
- interpolate wind data spatially and temporally
- provide wind data (tws, twd, gust) at a given location and time     
- cache processed grib data for faster subsequent accessp
- compute wind impact for cycling segments based on wind data and segment bearing
- adjust gust values to ensure they are not lower than the mean wind speed 
- provide detailed logging for debugging and analysis
- handle errors gracefully with informative messages
- structured for clarity and maintainability

"""

import time 
from datetime import timedelta, datetime, timezone 
import numpy as np
import pygrib
import math
import os
import glob 
import re 
import pickle
import logging
from typing import List, Dict, Optional, Any

# Build a wind representation from grib files
# require a list of valid grib files (0.25)     


class grib_essential_data :
    def __init__(self):
        # Wind initialisation
        self.lst_gribtimes = []
        self.lst_u10 = []
        self.lst_v10 = []
        self.lst_gust = []

class Grib:
    @staticmethod
    def _get_biwipy_cache_root() -> str:
        return os.environ.get("BIWIPY_CACHE_DIR") or os.path.expanduser("~/.cache/biwipy")

    @classmethod
    def _get_grib_cache_dir(cls) -> str:
        return os.path.join(cls._get_biwipy_cache_root(), "grib")

    def __init__(self, lfile, bcache=True, model="GFS", resolution=0.25, grib_limit=(0.0, 359.75, -90.0, 90.0)):
        start_time = time.time()
        self.model = model
        self.resolution = resolution
        if len(grib_limit) != 4:
            raise ValueError("grib_limit must be a 4-tuple: (lon_w, lon_e, lat_s, lat_n)")
        self.grib_limit = grib_limit
        self.inv_res = 1.0 / self.resolution

        # Wind initialisation
        self.Tot_time_pointvalidity = 0.0
        self.Tot_time_interpol = 0.0
        self.lst_gribtimes = []
        self.lst_u10 = []
        self.lst_v10 = []
        self.lst_gust = []
        self.table_longitude = []
        self.table_latitude = []
        self. nlatitude = 0
        self.nlongitude = 0
        self.grid_lon_min = 0.0
        self.grid_lon_max = 359.75
        self.grid_lat_min = -90.0
        self.grid_lat_max = 90.0
        self.run = None  # Will store the most recent run (e.g., "2026/03/09-12z")
        self.roughness_provider: Optional[Any] = None  # Optional RoughnessProvider for z0 lookup

        # Default lon convention by model (important when loading arrays from cache
        # where lat/lon grids are not always available to auto-detect convention).
        if str(self.model).upper() == "IFS":
            self.grid_lon_min = -180.0
            self.grid_lon_max = 179.75
        
        # Dynamic grid generation based on resolution
        # Assuming global coverage if grib_limit is default, otherwise usage might vary
        # For now, we preserve the global grid generation logic but parametrized
        
        step_inv = int(self.inv_res)
        lat_points = int(180 * step_inv) + 1  # e.g., 721 for 0.25
        lon_points = int(360 * step_inv)      # e.g., 1440 for 0.25

        for i in range(0, lat_points):
            self.table_latitude.append(float((i/step_inv-90)))
        if self.grid_lon_min < 0.0:
            for i in range(0, lon_points):
                self.table_longitude.append(float((i / step_inv) - 180.0))
        else:
            for i in range(0, lon_points):
                self.table_longitude.append(float((i/step_inv)))

        self. nlatitude = len(self.table_latitude)
        self.nlongitude = len(self.table_longitude)
        
        # grid dims initialized
        dircache = self._get_grib_cache_dir()
        if bcache:
            os.makedirs(dircache, exist_ok=True)
            logging.debug(f"Purge using cache directory: {dircache}")  
            purged = self._purge_cache(dircache, max_age_hours=48)
            if purged:
                logging.info(f"Purged {purged} expired cache files from {dircache}")
        
        # Process initial grib files if provided
        if lfile is not None:
            self._process_grib_files(lfile, bcache)
        
        # initialization complete
        windinit_run_time = time.time() - start_time   
        endm = 'Init wind end- time for wind initialization : {}'.format(round(windinit_run_time, 2))
        logging.info(endm)
    
    @staticmethod
    def _extract_message_group_key_and_time(grb):
        """
        Build a stable grouping key and target time for a GRIB message.

        Prefer run date/time + endStep so fields like IFS 10fg (often encoded on
        a step range like 14-15) align with 10u/10v at step 15.
        Fallback to validDate when step metadata is unavailable.
        """
        # Try forecast-step based grouping first.
        try:
            data_date = getattr(grb, 'dataDate', None)
            data_time = getattr(grb, 'dataTime', None)
            end_step = getattr(grb, 'endStep', None)
            if data_date is not None and data_time is not None and end_step is not None:
                run_dt = datetime.strptime(f"{int(data_date)}{int(data_time):04d}", "%Y%m%d%H%M")
                run_dt = run_dt.replace(tzinfo=timezone.utc)
                end_step_h = float(end_step)
                ctime = run_dt + timedelta(hours=end_step_h)
                return ((int(data_date), int(data_time), end_step_h), ctime)
        except Exception as e:
            logging.debug(f"Could not derive step-based key from message metadata: {e}")

        # Fallback: group by validDate directly.
        ctime = grb.validDate
        if ctime.tzinfo is None:
            ctime = ctime.replace(tzinfo=timezone.utc)
        return (("validDate", ctime), ctime)

    def _configure_grid_from_arrays(self, lats, lons):
        """Capture grid metadata (shape and lon convention) from GRIB arrays."""
        try:
            if lats is None or lons is None:
                return
            if len(getattr(lons, "shape", ())) != 2:
                return

            # Use actual grid shape from GRIB payload.
            self.nlatitude = int(lats.shape[0])
            self.nlongitude = int(lons.shape[1])

            # Longitudes can be either [0, 360) or [-180, 180).
            self.grid_lon_min = float(np.min(lons[0]))
            self.grid_lon_max = float(np.max(lons[0]))
            self.grid_lat_max = float(np.max(lats[:, 0]))
        except Exception as e:
            logging.debug(f"Could not configure grid metadata from arrays: {e}")

    def _normalize_lon_for_grid(self, lon):
        """Normalize longitude to the active GRIB grid convention."""
        if self.grid_lon_min < 0.0:
            # Grid convention [-180, 180)
            return ((lon + 180.0) % 360.0) - 180.0
        # Grid convention [0, 360)
        return lon % 360.0

    @staticmethod
    def _extract_date_from_path(filename):
        """
        Extract date key (YYYYMMDD) from a GRIB path.

        Supported patterns:
            - Parent directory containing YYYYMMDD
            - IFS basename: subset_*__YYYYMMDDHHMMSS-XXh-*-fc.grib2
        """
        # 1) Standard layout: date in parent directory
        parent_dir = os.path.basename(os.path.dirname(filename))
        date_match = re.search(r'(\d{8})', parent_dir)
        if date_match:
            return date_match.group(1)

        # 2) IFS subset layout: date encoded in basename timestamp
        basename = os.path.basename(filename)
        ifs_date_match = re.search(r'__(\d{8})\d{6}-\d+h-[^-]+-fc\.grib2$', basename)
        if ifs_date_match:
            return ifs_date_match.group(1)

        return None

    @staticmethod
    def _extract_run_from_filename(filename):
        """
        Extract the model run (date and hour) from a GRIB filename.
        
        Supported filename patterns:
            - gfs/YYYYMMDD/subset_*__gfs.tHHz.pgrb2.0p25.fNNN
            - ifs/YYYYMMDD/subset_*__YYYYMMDDHHMMSS-XXh-oper-fc.grib2
        Returns: String in format "YYYY/MM/DD-HHz" or None if parsing fails
        
        Examples:
            'gfs/20260309\\subset_4d896d33__gfs.t12z.pgrb2.0p25.f018' -> '2026/03/09-12z'
            'gfs/20260310\\gfs.t06z.pgrb2.0p25.f024' -> '2026/03/10-06z'
            'ifs/20260328/subset_a4b84a7c__20260328120000-15h-oper-fc.grib2' -> '2026/03/28-12z'
        """
        try:
            date_str = Grib._extract_date_from_path(filename)
            if not date_str:
                logging.debug(f"No date found in path: {filename}")
                return None

            year = date_str[0:4]
            month = date_str[4:6]
            day = date_str[6:8]

            # Extract run hour from GFS pattern (.tHHz.) or IFS timestamp (__YYYYMMDDHHMMSS-)
            basename = os.path.basename(filename)
            run_hour = None

            gfs_run_match = re.search(r'\.t(\d{2})z\.', basename)
            if gfs_run_match:
                run_hour = gfs_run_match.group(1)
            else:
                ifs_run_match = re.search(r'__(\d{8})(\d{2})\d{4}-\d+h-[^-]+-fc\.grib2$', basename)
                if ifs_run_match:
                    # Prefer date encoded in basename when available to avoid path ambiguity
                    date_str = ifs_run_match.group(1)
                    year = date_str[0:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    run_hour = ifs_run_match.group(2)

            if run_hour is None:
                logging.debug(f"No run hour found in filename: {basename}")
                return None

            # Format: "YYYY/MM/DD-HHz"
            return f"{year}/{month}/{day}-{run_hour}z"
        except Exception as e:
            logging.debug(f"Error extracting run from filename {filename}: {e}")
            return None
    
    def _process_grib_files(self, lfile, bcache=True):
        """
        Process grib files and update wind data lists.
        Handles cache management and file reading.
        
        :param lfile: List of grib file paths (duplicates will be automatically removed)
        :param bcache: Enable caching (default True)
        """
        dircache = self._get_grib_cache_dir()
        
        # Remove duplicate files while preserving order (Python 3.7+ dict preserves insertion order)
        unique_files = list(dict.fromkeys(lfile))
        if len(unique_files) < len(lfile):
            logging.info(f"Removed {len(lfile) - len(unique_files)} duplicate file(s) from input list")
        
        # Track the most recent run encountered
        runs_found = []
        
        for filename in unique_files:
            # Extract run information from filename
            run_info = self._extract_run_from_filename(filename)
            if run_info:
                runs_found.append(run_info)
            filepath=  os.path.basename(filename)
            date_str = self._extract_date_from_path(filename)
            if date_str:
                cache_subdir = os.path.join(dircache, date_str)
                os.makedirs(cache_subdir, exist_ok=True)
                picklefile = os.path.join(cache_subdir, filepath + '.pickle')
            else:
                # Fallback to flat structure if no date found
                logging.warning(f"No date found in path {filename}, using flat cache structure")
                picklefile = os.path.join(dircache, filepath + '.pickle')
            if (bcache) and (os.path.exists(picklefile)):
                cache_loaded = False
                try:
                    with open(picklefile, 'rb') as pk:
                        essential = pickle.load(pk)
                    try:
                        # Refresh atime/mtime so recent reads are not purged
                        os.utime(picklefile, None)
                    except OSError as e:
                        logging.debug(f"Could not touch cache file {picklefile}: {e}")

                    for eachtime in essential.lst_gribtimes:
                        self.lst_gribtimes.append(eachtime)
                    for eachu10 in essential.lst_u10:
                        self.lst_u10.append(eachu10)
                    for eachv10 in essential.lst_v10:
                        self.lst_v10.append(eachv10)
                    for eachgust in essential.lst_gust:
                        self.lst_gust.append(eachgust)
                    del essential
                    cache_loaded = True
                except (ModuleNotFoundError, AttributeError, EOFError, pickle.UnpicklingError) as e:
                    logging.warning(
                        f"Ignoring incompatible/corrupt cache file {picklefile}: {e}. Rebuilding from GRIB."
                    )
                    try:
                        os.remove(picklefile)
                    except OSError as rm_err:
                        logging.debug(f"Could not remove invalid cache file {picklefile}: {rm_err}")

                if cache_loaded:
                    continue

            grbs = pygrib.open(filename)  # type: ignore[attr-defined]
            n_values = int(grbs.messages)
            if n_values < 2:
                logging.error(f"File {filename} invalid: less than 2 GRIB messages (u10/v10 missing)")
                grbs.close()
                continue

            grbs.seek(0)
            if bcache:
                essential = grib_essential_data()

            # Read all messages and group by validDate, extracting by shortName
            times = {}
            for grb in grbs:
                group_key, ctime = self._extract_message_group_key_and_time(grb)
                # Safely obtain shortName from the message
                try:
                    shortname = getattr(grb, 'shortName', None)
                except Exception as e:
                    logging.error(f"Error obtaining shortName from GRIB message in {filename}: {e}")
                    continue

                if group_key not in times:
                    times[group_key] = {'ctime': ctime}

                try:
                    param_id = getattr(grb, 'paramId', None)
                    grb_name = getattr(grb, 'name', '')
                    is_gust_like = (
                        (isinstance(shortname, str) and (shortname == 'gust' or shortname.startswith('10fg')))
                        or param_id == 49
                        or (isinstance(grb_name, str) and 'gust' in grb_name.lower())
                    )
                    if shortname in ('10u', 'u10'):
                        u10_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['u10'] = u10_values
                    elif shortname in ('10v', 'v10'):
                        v10_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['v10'] = v10_values
                    elif is_gust_like:
                        gust_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['gust'] = gust_values
                    else:
                        # ignore other parameters
                        continue
                except Exception as e:
                    logging.error(f"Error reading data for {shortname} at {ctime} in {filename}: {e}")
                    continue

            # close grib file
            grbs.close()

            # Now iterate times in order and append arrays; gust is mandatory
            for _, entry in sorted(times.items(), key=lambda item: item[1]['ctime']):
                ctime = entry['ctime']
                if 'u10' not in entry or 'v10' not in entry:
                    logging.error(f"Fichier {filename} invalide pour {ctime}: u10 ou v10 manquant")
                    continue
                if 'gust' not in entry:
                    # Some historical IFS subsets do not provide 10fg/10fg3.
                    # Keep the frame and reconstruct a neutral gust from U/V.
                    entry['gust'] = np.sqrt(entry['u10'] ** 2 + entry['v10'] ** 2)
                    logging.warning(
                        f"Fichier {filename}: gust manquant pour {ctime}, "
                        "fallback gust=sqrt(u10^2+v10^2) applique"
                    )

                self.lst_gribtimes.append(ctime)
                self.lst_u10.append(entry['u10'])
                self.lst_v10.append(entry['v10'])
                self.lst_gust.append(entry['gust'])

                if (bcache):
                    essential.lst_gribtimes.append(ctime)
                    essential.lst_u10.append(entry['u10'])
                    essential.lst_v10.append(entry['v10'])
                    essential.lst_gust.append(entry['gust'])
            #print (picklefile)
            if (bcache):
                with open(picklefile, 'wb') as f:  # open a text file
                  pickle.dump(essential, f,protocol=pickle.HIGHEST_PROTOCOL) # serialize the essential data
                  del essential
        
        # Sort all data by timestamp after processing all files
        # This ensures correct temporal ordering even if files were loaded in wrong order
        if self.lst_gribtimes:
            sorted_indices = sorted(range(len(self.lst_gribtimes)), key=lambda i: self.lst_gribtimes[i])
            self.lst_gribtimes = [self.lst_gribtimes[i] for i in sorted_indices]
            self.lst_u10 = [self.lst_u10[i] for i in sorted_indices]
            self.lst_v10 = [self.lst_v10[i] for i in sorted_indices]
            self.lst_gust = [self.lst_gust[i] for i in sorted_indices]
            logging.debug(f"Sorted {len(self.lst_gribtimes)} timestamps after loading files")
        
        # Store the most recent run (lexicographically largest, which corresponds to most recent date/time)
        if runs_found:
            self.run = max(runs_found)
            logging.info(f"Most recent model run: {self.run}")
        else:
            logging.warning("No valid run information could be extracted from filenames")

    def update_wind(self, lfile, bcache=True):
        """
        Update wind representation with new grib files.
        
        Handles duplicate timestamps by replacing old data with new data
        for the same valid times.
        
        :param lfile: List of new grib file paths to process (duplicates will be automatically removed)
        :param bcache: Enable caching (default True)
        
        Example:
            mygrib = Grib(initial_files)
            # Later, add new files
            mygrib.update_wind(new_files)
        """
        start_time = time.time()
        
        # Remove duplicate files while preserving order
        unique_files = list(dict.fromkeys(lfile))
        if len(unique_files) < len(lfile):
            logging.info(f"Removed {len(lfile) - len(unique_files)} duplicate file(s) from update list")
        
        logging.info(f"Starting wind data update with {len(unique_files)} new file(s)")
        
        # Track runs from new files
        runs_found = []
        
        # Process new files into temporary lists
        new_times = []
        new_u10 = []
        new_v10 = []
        new_gust = []
        
        dircache = self._get_grib_cache_dir()
        if bcache:
            os.makedirs(dircache, exist_ok=True)
        
        for filename in unique_files:
            # Extract run information from filename
            run_info = self._extract_run_from_filename(filename)
            if run_info:
                runs_found.append(run_info)
            
            filepath = os.path.basename(filename)
            date_str = self._extract_date_from_path(filename)
            if date_str:
                cache_subdir = os.path.join(dircache, date_str)
                os.makedirs(cache_subdir, exist_ok=True)
                picklefile = os.path.join(cache_subdir, filepath + '.pickle')
            else:
                logging.warning(f"No date found in path {filename}, using flat cache structure")
                picklefile = os.path.join(dircache, filepath + '.pickle')
            
            if (bcache) and (os.path.exists(picklefile)):
                cache_loaded = False
                try:
                    with open(picklefile, 'rb') as pk:
                        essential = pickle.load(pk)
                    try:
                        os.utime(picklefile, None)
                    except OSError as e:
                        logging.debug(f"Could not touch cache file {picklefile}: {e}")

                    new_times.extend(essential.lst_gribtimes)
                    new_u10.extend(essential.lst_u10)
                    new_v10.extend(essential.lst_v10)
                    new_gust.extend(essential.lst_gust)
                    del essential
                    cache_loaded = True
                except (ModuleNotFoundError, AttributeError, EOFError, pickle.UnpicklingError) as e:
                    logging.warning(
                        f"Ignoring incompatible/corrupt cache file {picklefile}: {e}. Rebuilding from GRIB."
                    )
                    try:
                        os.remove(picklefile)
                    except OSError as rm_err:
                        logging.debug(f"Could not remove invalid cache file {picklefile}: {rm_err}")

                if cache_loaded:
                    continue

            grbs = pygrib.open(filename)  # type: ignore[attr-defined]
            n_values = int(grbs.messages)
            if n_values < 2:
                logging.error(f"File {filename} invalid: less than 2 GRIB messages (u10/v10 missing)")
                grbs.close()
                continue

            grbs.seek(0)
            if bcache:
                essential = grib_essential_data()

            times = {}
            for grb in grbs:
                group_key, ctime = self._extract_message_group_key_and_time(grb)
                try:
                    shortname = getattr(grb, 'shortName', None)
                except Exception as e:
                    logging.error(f"Error obtaining shortName from GRIB message in {filename}: {e}")
                    continue

                if group_key not in times:
                    times[group_key] = {'ctime': ctime}

                try:
                    param_id = getattr(grb, 'paramId', None)
                    grb_name = getattr(grb, 'name', '')
                    is_gust_like = (
                        (isinstance(shortname, str) and (shortname == 'gust' or shortname.startswith('10fg')))
                        or param_id == 49
                        or (isinstance(grb_name, str) and 'gust' in grb_name.lower())
                    )
                    if shortname in ('10u', 'u10'):
                        u10_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['u10'] = u10_values
                    elif shortname in ('10v', 'v10'):
                        v10_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['v10'] = v10_values
                    elif is_gust_like:
                        gust_values, lats, lons = grb.data()
                        self._configure_grid_from_arrays(lats, lons)
                        times[group_key]['gust'] = gust_values
                    else:
                        continue
                except Exception as e:
                    logging.error(f"Error reading data for {shortname} at {ctime} in {filename}: {e}")
                    continue

            grbs.close()

            for _, entry in sorted(times.items(), key=lambda item: item[1]['ctime']):
                ctime = entry['ctime']
                if 'u10' not in entry or 'v10' not in entry:
                    logging.error(f"Fichier {filename} invalide pour {ctime}: u10 ou v10 manquant")
                    continue
                if 'gust' not in entry:
                    # Some historical IFS subsets do not provide 10fg/10fg3.
                    # Keep the frame and reconstruct a neutral gust from U/V.
                    entry['gust'] = np.sqrt(entry['u10'] ** 2 + entry['v10'] ** 2)
                    logging.warning(
                        f"Fichier {filename}: gust manquant pour {ctime}, "
                        "fallback gust=sqrt(u10^2+v10^2) applique"
                    )

                new_times.append(ctime)
                new_u10.append(entry['u10'])
                new_v10.append(entry['v10'])
                new_gust.append(entry['gust'])

                if (bcache):
                    essential.lst_gribtimes.append(ctime)
                    essential.lst_u10.append(entry['u10'])
                    essential.lst_v10.append(entry['v10'])
                    essential.lst_gust.append(entry['gust'])
            
            if (bcache):
                with open(picklefile, 'wb') as f:
                    pickle.dump(essential, f, protocol=pickle.HIGHEST_PROTOCOL)
                    del essential
        
        # Merge new data with existing data, replacing duplicates
        # Create a dict indexed by time for efficient lookup and replacement
        merged_data = {}
        
        # First, add existing data
        for i, ctime in enumerate(self.lst_gribtimes):
            merged_data[ctime] = {
                'u10': self.lst_u10[i],
                'v10': self.lst_v10[i],
                'gust': self.lst_gust[i]
            }
        
        # Then, add/replace with new data (new data takes precedence)
        duplicates = 0
        for i, ctime in enumerate(new_times):
            if ctime in merged_data:
                duplicates += 1
                logging.info(f"Replacing wind data for timestamp {ctime}")
            merged_data[ctime] = {
                'u10': new_u10[i],
                'v10': new_v10[i],
                'gust': new_gust[i]
            }
        
        # Sort by time and rebuild lists
        sorted_times = sorted(merged_data.keys())
        self.lst_gribtimes = sorted_times
        self.lst_u10 = [merged_data[t]['u10'] for t in sorted_times]
        self.lst_v10 = [merged_data[t]['v10'] for t in sorted_times]
        self.lst_gust = [merged_data[t]['gust'] for t in sorted_times]
        
        # Update run with most recent from new files or keep existing if newer
        if runs_found:
            new_most_recent = max(runs_found)
            if self.run is None or new_most_recent > self.run:
                self.run = new_most_recent
                logging.info(f"Updated model run to: {self.run}")
        
        update_run_time = time.time() - start_time
        endm = f'Wind data update complete - Added {len(new_times)} entries, replaced {duplicates} duplicates, total time: {round(update_run_time, 2)}s'
        logging.info(endm)
        logging.info(f"Total wind data points: {len(self.lst_gribtimes)}, time range: {self.lst_gribtimes[0]} to {self.lst_gribtimes[-1]}")

    @staticmethod
    def interpolate_temporal(values, times, time_point):
        # Convertir les temps en timestamps pour l'interpolation
        time_stamps = times.astype('datetime64[ns]').astype(int)
        time_point_stamp = time_point.astype('datetime64[ns]').astype(int)
        return np.interp(time_point_stamp, time_stamps, values)

    @staticmethod
    def bilinear_interpolation(x, y, points):
        '''Interpolate (x,y) from values associated with four points.

        The four points are a list of four triplets:  (x, y, value).
        The four points can be in any order.  They should form a rectangle.

            >>> bilinear_interpolation(12, 5.5,
            ...                        [(10, 4, 100),
            ...                         (20, 4, 200),
            ...                         (10, 6, 150),
            ...                         (20, 6, 300)])
            165.0
        '''
        # See formula at:  http://en.wikipedia.org/wiki/Bilinear
        points = sorted(points)               # order points by x, then by y
        (x1, y1, q11), (_x1, y2, q12), (x2, _y1, q21), (_x2, _y2, q22) = points
        # print ("POINTS:",points)
        # print (x1,x,x2,y1,y,y2)

        if x1 != _x1 or x2 != _x2 or y1 != _y1 or y2 != _y2:
            raise ValueError('points do not form a rectangle')
        if not x1 <= x <= x2 or not y1 <= y <= y2:

            raise ValueError('(x, y) not within the rectangle')

        return (q11 * (x2 - x) * (y2 - y) +
                q21 * (x - x1) * (y2 - y) +
                q12 * (x2 - x) * (y - y1) +
                q22 * (x - x1) * (y - y1)
                ) / ((x2 - x1) * (y2 - y1) + 0.0)

    def _purge_cache(self, dircache, max_age_hours=48):
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        try:
            # Scan the main cache directory
            with os.scandir(dircache) as it:
                for entry in it:
                    if entry.is_dir():
                        # Process subdirectories (date folders YYYYMMDD)
                        try:
                            with os.scandir(entry.path) as subdir_it:
                                for subentry in subdir_it:
                                    if not subentry.is_file():
                                        continue
                                    if not subentry.name.endswith('.pickle'):
                                        continue
                                    try:
                                        if subentry.stat().st_atime < cutoff:
                                            logging.debug(f"Removing expired cache file: {subentry.path}")
                                            os.remove(subentry.path)
                                            removed += 1
                                        else:
                                            logging.debug(f"Keeping recent cache file: {subentry.path}")
                                    except OSError as e:
                                        logging.warning(f"Failed to remove cache file {subentry.path}: {e}")
                            # Try to remove empty subdirectory
                            try:
                                os.rmdir(entry.path)
                                logging.debug(f"Removed empty cache subdirectory: {entry.path}")
                            except OSError:
                                pass  # Directory not empty or other error, ignore
                        except OSError as e:
                            logging.warning(f"Failed to scan cache subdirectory {entry.path}: {e}")
                    elif entry.is_file():
                        # Handle files in flat structure (backward compatibility)
                        if not entry.name.endswith('.pickle'):
                            continue
                        try:
                            if entry.stat().st_atime < cutoff:
                                logging.debug(f"Removing expired cache file: {entry.path}")
                                os.remove(entry.path)
                                removed += 1
                            else:
                                logging.debug(f"Keeping recent cache file: {entry.path}")
                        except OSError as e:
                            logging.warning(f"Failed to remove cache file {entry.path}: {e}")
        except FileNotFoundError:
            return 0
        return removed

    # faster than grib_value ... ????? 
    def grib_uvgust(self, step):
        # x lon y lat - returns lambda for (u, v, gust)
        inv_res = self.inv_res
        nlon = self.nlongitude
        lon_min = self.grid_lon_min
        lat_max = self.grid_lat_max
        return lambda x, y: (
            (self.lst_u10[step])[int(round((lat_max-y)*inv_res))][int(round((self._normalize_lon_for_grid(x)-lon_min)*inv_res))%nlon].item(),
            (self.lst_v10[step])[int(round((lat_max-y)*inv_res))][int(round((self._normalize_lon_for_grid(x)-lon_min)*inv_res))%nlon].item(),
            (self.lst_gust[step])[int(round((lat_max-y)*inv_res))][int(round((self._normalize_lon_for_grid(x)-lon_min)*inv_res))%nlon].item()
        )

    # Note: debug helpers removed to reduce verbosity. Only adjustment logging remains.


# Wind direction and speed for a given location at specified time
# input parameter  datetime item, float latitude ,  float longitude a
# returns a tuple with true wind direction (twd) expressed in degrees and true wind speed (tws) expressed in meters per second
# or None if running out of temporal/geographic grib scope.


    def get_wind_at(self, tp, lat_point, lon_point, return_raw=False):
        #if (tp.tzinfo != None) :
        #    tp=tp.replace(tzinfo=None)
        # convert all the date in utc (Naive date is assumed to be locale) 
        tp_utc=tp.astimezone(timezone.utc)
        nptp = np.datetime64(tp_utc.replace(tzinfo=None))
        # trouver les time steps encadrant l'heure
        time0 = time.time()
        lon_point = self._normalize_lon_for_grid(lon_point)
        # trouver les heures de grib concernés
        if (self.lst_gribtimes[0]) > tp_utc :
            logging.error(f"OUT of GRIB : Requested time {tp_utc} before grib data start {self.lst_gribtimes[0]}")
            return (None)
        not_found = True
        idx = 1
        while (not_found):
            if idx >= len(self.lst_gribtimes):
                logging.error(f"OUT of GRIB :Requested time {tp_utc} after grib data end {self.lst_gribtimes[-1]}")
                return (None)
            if (self.lst_gribtimes[idx]) >= tp_utc :
                not_found = False
            else:
                idx = idx+1
        idx1 = idx-1
        idx2 = idx
        t1 = (self.lst_gribtimes[idx1]).replace(tzinfo=None) # temps t1
        t2 = (self.lst_gribtimes[idx2]).replace(tzinfo=None) # temps t2
        
        # Check if point is on grid using resolution
        inv_res = self.inv_res
        res = self.resolution
        
        if ((lat_point*inv_res).is_integer()) and ((lon_point*inv_res).is_integer()):
            # le point est le sur le grib :  pas d'interpolation spatiale
            (u10_1, v10_1, gust_1) = self.grib_uvgust(idx1)(lon_point, lat_point)
            (u10_2, v10_2, gust_2) = self.grib_uvgust(idx2)(lon_point, lat_point)
        else:
            # trouver les 4 points du grib encadrant le point recherché
            def afloor(x): return math.floor(x*inv_res)/inv_res
            def aceil(x): return math.ceil(x*inv_res)/inv_res
            la1 = afloor(lat_point)
            la2 = aceil(lat_point)
            lo1 = afloor(lon_point)
            lo2 = aceil(lon_point)
            if (la1 == la2):
                la2 = la1+res
            if (lo1 == lo2):
                lo2 = lo1+res

            # print ("B", la1,la2,lo1,lo2)
            # print ('C',lat_point,lon_point)
            
            # valeurs de u, v et gust au 4 points à t1
    
            gv = self.grib_uvgust(idx1)
            (upointA1, vpointA1, gustpointA1) = gv(lo1, la1)
            (upointB1, vpointB1, gustpointB1) = gv(lo2, la1)
            (upointC1, vpointC1, gustpointC1) = gv(lo1, la2)
            (upointD1, vpointD1, gustpointD1) = gv(lo2, la2)
            # interpolation de u et v aux poins recherchés à t1
            upointsquare1 = [(lo1, la1, upointA1), (lo2, la1, upointB1),
                             (lo1, la2, upointC1), (lo2, la2, upointD1)]
            u10_1 = Grib.bilinear_interpolation(
                lon_point, lat_point, upointsquare1)
            vpointsquare1 = [(lo1, la1, vpointA1), (lo2, la1, vpointB1),
                             (lo1, la2, vpointC1), (lo2, la2, vpointD1)]
            v10_1 = Grib.bilinear_interpolation(
                lon_point, lat_point, vpointsquare1)
            
            # interpolation du gust aux points recherchés à t1
            gustsquare1 = [(lo1, la1, gustpointA1), (lo2, la1, gustpointB1),
                           (lo1, la2, gustpointC1), (lo2, la2, gustpointD1)]
            gust_1 = Grib.bilinear_interpolation(
                lon_point, lat_point, gustsquare1)
            
            # valeurs de U, V et gust au 4 points  à t2

            gv = self.grib_uvgust(idx2)
            (upointA2, vpointA2, gustpointA2) = gv(lo1, la1)
            (upointB2, vpointB2, gustpointB2) = gv(lo2, la1)
            (upointC2, vpointC2, gustpointC2) = gv(lo1, la2)
            (upointD2, vpointD2, gustpointD2) = gv(lo2, la2)
            # interpolation de u et v aux poins recherchés à t2
            upointsquare2 = [(lo1, la1, upointA2), (lo2, la1, upointB2),
                             (lo1, la2, upointC2), (lo2, la2, upointD2)]
            u10_2 = Grib.bilinear_interpolation(
                lon_point, lat_point, upointsquare2)
            vpointsquare2 = [(lo1, la1, vpointA2), (lo2, la1, vpointB2),
                             (lo1, la2, vpointC2), (lo2, la2, vpointD2)]
            v10_2 = Grib.bilinear_interpolation(
                lon_point, lat_point, vpointsquare2)
            
            # interpolation du gust aux points recherchés à t2
            gustsquare2 = [(lo1, la1, gustpointA2), (lo2, la1, gustpointB2),
                           (lo1, la2, gustpointC2), (lo2, la2, gustpointD2)]
            gust_2 = Grib.bilinear_interpolation(
                lon_point, lat_point, gustsquare2)
            
        # interpolation temporelle
        Ti1 = np.array([t1, t2])
        u_int = Grib.interpolate_temporal(
            [u10_1, u10_2], Ti1, nptp)
        v_int = Grib.interpolate_temporal(
            [v10_1, v10_2], Ti1, nptp)
        gust_int = Grib.interpolate_temporal(
            [gust_1, gust_2], Ti1, nptp)
        
        tws = round((np.sqrt(u_int**2 + v_int**2)), 2)
        twd = round((np.degrees(np.arctan2(u_int, v_int)) + 180) % 360, 2)

        gust_before = round(gust_int, 2)
        gust = gust_before

        # Ensure gust is not lower than the (interpolated) wind speed
        adjusted = False
        if gust < tws:
            adjusted = True
            gust = tws
            logging.debug(f"Adjusted gust to tws: time={tp_utc}, lat={lat_point}, lon={lon_point}, tws={tws}, gust_before={gust_before}, gust_after={gust}")

        time1 = time.time()
        self.Tot_time_interpol = self.Tot_time_interpol+(time1-time0)
        if return_raw:
            # return gust_before as the 4th element for diagnostics (pre-adjustment)
            return (tws, twd, gust, gust_before)
        return (tws, twd, gust)

    def wind_component_along(self, tws, twd, bearing):
        """
        Compute wind component along a given bearing.

        tws: True Wind Speed in m/s
        twd: True Wind Direction in degrees (direction FROM which the wind blows)
        bearing: travel/course direction in degrees (direction TO which the vessel/vehicle moves)

        Returns the wind projected onto the travel axis (m/s).
        Positive = tailwind (assisting), Negative = headwind (opposing).
        """

        angle = np.radians(twd - bearing + 180)
        # +180 because TWD is the wind's ORIGIN direction; we want direction TOWARD the vehicle
        along = tws * np.cos(angle)
        return along

    def purge_before(self, dt):
        """
        Remove all timesteps strictly before the given datetime.
        
        :param dt: datetime to use as cutoff (timesteps where t < dt are removed)
        :return: int, number of removed timesteps
        """
        count_removed = 0
        indices_to_keep = []
        
        for i, t in enumerate(self.lst_gribtimes):
            if t >= dt:
                indices_to_keep.append(i)
            else:
                count_removed += 1
        
        # Filter all arrays to keep only the selected indices
        self.lst_gribtimes = [self.lst_gribtimes[i] for i in indices_to_keep]
        self.lst_u10  = [self.lst_u10[i] for i in indices_to_keep]
        self.lst_v10  = [self.lst_v10[i] for i in indices_to_keep]
        self.lst_gust = [self.lst_gust[i] for i in indices_to_keep]
        
        return count_removed

    def purge_between(self, dt1, dt2):
        """
        Remove all timesteps within the closed interval [dt1, dt2] inclusive.
        
        :param dt1: datetime for start of interval
        :param dt2: datetime for end of interval
        :return: int, number of removed timesteps
        :raises ValueError: if dt1 > dt2
        """
        if dt1 > dt2:
            raise ValueError(f"dt1 ({dt1}) must be <= dt2 ({dt2})")
        
        count_removed = 0
        indices_to_keep = []
        
        for i, t in enumerate(self.lst_gribtimes):
            if dt1 <= t <= dt2:
                count_removed += 1
            else:
                indices_to_keep.append(i)
        
        # Filter all arrays to keep only the selected indices
        self.lst_gribtimes = [self.lst_gribtimes[i] for i in indices_to_keep]
        self.lst_u10  = [self.lst_u10[i] for i in indices_to_keep]
        self.lst_v10  = [self.lst_v10[i] for i in indices_to_keep]
        self.lst_gust = [self.lst_gust[i] for i in indices_to_keep]
        
        return count_removed
    
# Calculate wind impact for cycling segments    
# input parameters : datetime item, float latitude , float longitude , float bearing (degrees)
# returns a dict with wind impact data  
# For the moment doesn't take in consideration the law of the wall (wind speed variation with height)
# Wwind speed obeys the law of the wall, so the wind speed at 1.5m is u * ln(1.5/z) / ln(10/z), 
# where u is the weind speed at 10 m and z the roughness length z. 
# As z=0,1 is the typical value for open terrain, the factor is about 0.58


    k_roughness= math.log (1.5/0.1) / math.log (10/0.1)  # roughness length z=0.1 m
    def calculate_cycling_wind_impact(self, tp, lat_point, lon_point, bearing, ratio_wind=0.10, rugosite=None):
        """
        Calculate the wind impact for a cycling segment.

        :param tws: True Wind Speed (m/s)
        :param twd: True Wind Direction (degrees, direction FROM which the wind blows)
        :param gust: Gust Speed (m/s, already adjusted so gust >= tws)
        :param bearing: GPS segment bearing (degrees, direction TO which the cyclist moves)
        :param rugosite: Roughness length z0 in meters (default None -> use internal 0.1m)
        :return: dict containing headwind/tailwind components and a simple effort index
        """

        # 0. Get wind
        logging.debug(f"Calculating wind impact at time {tp}, lat {lat_point}, lon {lon_point}, bearing {bearing}")
        res= self.get_wind_at(tp, lat_point, lon_point)
        if res is None:
            logging.error(f"Wind data unavailable for time {tp}, lat {lat_point}, lon {lon_point}")
            return None 
        else :
            tws, twd, gust = res[0], res[1], res[2]
        
        # Normalize wind from 10 m to ground level 
        # fisrt approch use a coefficient 
        # in the future use a logarithmic profile with roughness length or overpy api
        if rugosite is not None and rugosite > 0:
            ground_level_factor = math.log(1.5/rugosite) / math.log(10/rugosite)
        else:
            ground_level_factor = Grib.k_roughness
        
        tws_norm = tws * ground_level_factor
        gust_norm = gust * ground_level_factor


        # 1. Compute incidence angle (radians)
        # Normalize the angular difference to the range [0, 180]
        diff_angle = (twd - bearing) % 360
        if diff_angle > 180:
            diff_angle = 360 - diff_angle
        rad_diff = math.radians(diff_angle)

        # 2. Project mean wind along the travel axis (headwind/tailwind)
        # Positive = headwind, Negative = tailwind
        wind_along = tws_norm * math.cos(rad_diff)

        # 3. Project gust along the travel axis
        gust_along = gust_norm * math.cos(rad_diff)

        # 4. Lateral (crosswind) component — important for stability and aerodynamic drag
        crosswind = tws_norm * math.sin(rad_diff)

        # 5. Compute an "effective" along-axis wind that weights gusts more heavily
        # because cyclists slow down more during gusts than they re-accelerate afterwards.
        # A ratio of 10% of the gust surplus is a reasonable baseline.
        effective_wind_along = wind_along + ratio_wind * (gust_along - wind_along)
        return {
            "tws_m_s": round(tws_norm, 2),
            "twd_deg": round(twd, 2),
            "gust_m_s": round(gust_norm, 2),
            "headwind_m_s": round(wind_along, 2),
            "gust_along_m_s": round(gust_along, 2),
            "effective_wind_m_s": round(effective_wind_along, 2),
            "crosswind_m_s": round(abs(crosswind), 2),
            "is_headwind": wind_along > 0
        }

if __name__ == "__main__":
    # import findgribfiles
    import grib_finder as findgribfiles
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Configuration chemin
    if os.name == 'posix':
        hdir = "/mnt/nasdocker/grib/data/"
    else:
        hdir = "G:/grib/data/"
    mypas = 1

    date_exemple = datetime(2026, 1, 5, 8, 14, 0, tzinfo=timezone.utc)
    intervalle_exemple = 8

    # build grib list and load
    try:
        gribs_list = findgribfiles.build_grib_list(hdir, date_exemple, mypas, intervalle_exemple)
    except Exception as e:
        logging.error(f"Error building grib list: {e}")
        raise
    mygrib = Grib(gribs_list, bcache=True)
    
    logging.getLogger().setLevel(logging.INFO)

    lats = [43.56, 43.55]
    lons = [1.29, 1.17]

    mydate = date_exemple
    while mydate <= date_exemple + timedelta(hours=intervalle_exemple):
        logging.info(f"  Date: {mydate}")
        for (lat, lon) in zip(lats, lons):
 
            result = mygrib.get_wind_at(mydate, lat, lon)
            bearing=75.0  # example bearing
            impact=mygrib.calculate_cycling_wind_impact(mydate, lat, lon, bearing)
            assert impact is not None
            logging.info(f"Point lat={lat}, lon={lon} => TWS={impact['tws_m_s']} m/s, TWD={impact['twd_deg']}°, Gust={impact['gust_m_s']} m/s")
            
            if impact["is_headwind"]:
                wind_type = "Headwind"
            else:
                wind_type = "Tailwind"
            logging.info(
                "Impact %s: %s m/s, gust_along: %s m/s, effective wind: %s m/s, crosswind: %s m/s",
                wind_type,
                impact["headwind_m_s"],
                impact["gust_along_m_s"],
                impact["effective_wind_m_s"],
                impact["crosswind_m_s"],
            )

        mydate += timedelta(hours=1)

        
        

