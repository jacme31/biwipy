#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 15 14:53:46 2025

@author: Jacme31
"""

from datetime import datetime, timedelta, timezone
from herbie.latest import HerbieWait
from typing import List, Dict, Literal, TypedDict
import math
import glob
import time
import os
import pygrib
import logging


IFS_PRIORITY = ['google','azure', 'aws', 'ecwmf']


class IFSRef(TypedDict):
    run_datetime: datetime
    run_hour: int
    fxx: int
    product: str
    valid_time: datetime


def _ifs_product_for_run_hour(run_hour: int) -> str:
    return "oper" if run_hour in (0, 12) else "scda"


def _is_valid_ifs_fxx(run_hour: int, fxx: int) -> bool:
    if fxx < 0:
        return False
    if fxx == 0:
        return True
    if run_hour in (0, 12):
        if fxx <= 144:
            return fxx % 3 == 0
        if fxx <= 360:
            return fxx % 6 == 0
        return False
    # 06z and 18z runs
    if run_hour in (6, 18):
        return fxx <= 144 and fxx % 3 == 0
    return False

def find_gribs_for_interpolation(date_cible: datetime, pas: Literal[1, 3] = 1, intervalle_h: int = 6) -> List[str]:
    """Find the GFS GRIB file references required to interpolate
    the target datetime plus the time interval, taking F000 into account when
    relevant. Returns the most recent forecast references covering the period.

    :param date_cible: The datetime to cover (must be UTC or will be converted).
    :param pas: Time step granularity (1 = hourly up to F120 then 3h, 3 = 3h only for h>0)
    :param intervalle_h: Time interval in hours after the target datetime (actual ride duration).
                        Note: An automatic margin (3h for pas=3, 1h for pas=1) is added to ensure
                        temporal interpolation works at the end of the period.
    :return: A list of strings in the format "YYYYMMDD:xxZ:hhh".
    
    Example:
        # For a 2-hour ride starting at 14:00 UTC with pas=3:
        # - User specifies intervalle_h=2
        # - Function automatically requests data until 14:00 + 2h + 3h (margin) = 19:00
        # - Returns GRIB files covering 12:00, 15:00, 18:00 (allows interpolation throughout)
    """
    
    # --- 1. Prepare dates and constants ---
    
    if date_cible.tzinfo is None or date_cible.tzinfo.utcoffset(date_cible) is None:
        date_cible_utc = date_cible.replace(tzinfo=timezone.utc)
    else:
        date_cible_utc = date_cible.astimezone(timezone.utc)   
    
    if (pas == 3):
        #  Adjust date_période_utc to the nearest lower 3-hour mark
        debut_periode_utc = date_cible_utc -  timedelta(hours=3)
    else:
        debut_periode_utc = date_cible_utc
    
    # Add one extra time step after the target period to ensure interpolation works
    # even at the end of the period (we need timestamps before AND after for interpolation)
    margin_h = 3 if pas == 3 else 1
    fin_periode_utc = date_cible_utc + timedelta(hours=intervalle_h) + timedelta(hours=margin_h)
    
    logging.info(f"period UTC: {debut_periode_utc} to {date_cible_utc + timedelta(hours=intervalle_h)} "
                f"(+{margin_h}h margin for interpolation)")
    RUN_HEURES = [0, 6, 12, 18]
    DELAI_DISPONIBILITE_H = 4.5 
    MAX_FORECAST_H = 384

    # pas: granularité des pas (1 = 1h jusqu'à F120 puis 3h; 3 = uniquement pas de 3h pour h>0)
    if pas not in (1, 3):
        raise ValueError("Le paramètre 'pas' doit valoir 1 ou 3")
    meilleurs_gribs_par_heure: Dict[datetime, tuple[datetime, str]] = {}
    maintenant_utc = datetime.now(timezone.utc)

    # --- 2. Determine the range of runs to analyze ---
    date_max_run = fin_periode_utc - timedelta(hours=MAX_FORECAST_H)
    date_run_iter = datetime(date_max_run.year, date_max_run.month, date_max_run.day, 
                             tzinfo=timezone.utc)
    while date_run_iter <= fin_periode_utc + timedelta(days=1):
        for heure_run in RUN_HEURES:
            date_heure_run = date_run_iter.replace(hour=heure_run)
            # Check availability
            date_disponibilite = date_heure_run + timedelta(hours=DELAI_DISPONIBILITE_H)
            if date_disponibilite > maintenant_utc:
                continue
            # Compute raw durations (in floating hours) relative to the run
            duration_h_min = (debut_periode_utc - date_heure_run).total_seconds() / 3600
            duration_h_max = (fin_periode_utc - date_heure_run).total_seconds() / 3600        
            # --- Compute integer forecast hour bounds (Fhhh) to bracket ---
            # h_debut: lower-or-equal integer forecast hour (math.floor)
            h_debut = math.floor(duration_h_min)
            # h_fin: upper-or-equal integer forecast hour (math.ceil)
            h_fin = math.ceil(duration_h_max)
            # F000 is the minimum bound for GFS
            h_debut = max(0, h_debut)
            # Ensure h_fin does not exceed the maximum
            h_fin = min(MAX_FORECAST_H, h_fin)
            # --- 3. Iterate over valid hourly slices in [h_debut, h_fin] ---
            for h in range(h_debut, h_fin + 1):
                # Apply step rules according to `pas`
                is_valid_step = False
                if h == 0:
                    # F000 (initial analysis) is always valid
                    is_valid_step = True
                else:
                    if pas == 1:
                        # pas=1 : pas 1h jusqu'à F120, puis pas 3h
                        if 1 <= h <= 120:
                            is_valid_step = True
                        elif h > 120 and h % 3 == 0:
                            is_valid_step = True
                    else:
                        # pas=3 : uniquement pas de 3h pour h>0
                        if h > 0 and h % 3 == 0:
                            is_valid_step = True
                if not is_valid_step:
                    continue
                heure_forecast = date_heure_run + timedelta(hours=h)
                # Create the GRIB reference
                date_str = date_heure_run.strftime('%Y%m%d')
                run_str = f"{heure_run:02}z"
                tranche_h_str = f"{h:03}"
                reference_grib = f"{date_str}:{run_str}:{tranche_h_str}"
                # Priority logic: the most recent run overrides older ones for the same forecast hour
                meilleurs_gribs_par_heure[heure_forecast] = (date_heure_run, reference_grib)
        # Move to the next day
        date_run_iter += timedelta(days=1)
        
    # --- 4. Return the list sorted by validity hour ---
    references_finales_triees = sorted([
        (heure, data[1]) 
        for heure, data in meilleurs_gribs_par_heure.items()
    ])
    
    result = [item[1] for item in references_finales_triees]
    
    # --- 5. Safety check: ensure at least 2 timestamps for temporal interpolation ---
    if len(result) < 2:
        logging.warning(f"Only {len(result)} GRIB file(s) found for interpolation. "
                       f"At least 2 timestamps are required for temporal interpolation. "
                       f"Consider increasing intervalle_h (currently {intervalle_h}h).")
        # If only 1 file found, try to extend the period
        if len(result) == 1 and meilleurs_gribs_par_heure:
            # Get the single timestamp we have
            single_time = references_finales_triees[0][0]
            # Try to add the next valid time step
            next_time = single_time + timedelta(hours=(3 if pas == 3 else 1))
            # Search for a GRIB covering this next time
            for date_run_iter_retry in [single_time - timedelta(days=1), single_time, single_time + timedelta(days=1)]:
                for heure_run in RUN_HEURES:
                    date_heure_run = date_run_iter_retry.replace(hour=heure_run, minute=0, second=0, microsecond=0)
                    date_disponibilite = date_heure_run + timedelta(hours=DELAI_DISPONIBILITE_H)
                    if date_disponibilite > maintenant_utc:
                        continue
                    # Calculate forecast hour for next_time
                    h_next = int((next_time - date_heure_run).total_seconds() / 3600)
                    if h_next < 0 or h_next > MAX_FORECAST_H:
                        continue
                    # Check if this is a valid step
                    is_valid = False
                    if h_next == 0:
                        is_valid = True
                    elif pas == 1:
                        if 1 <= h_next <= 120 or (h_next > 120 and h_next % 3 == 0):
                            is_valid = True
                    else:  # pas == 3
                        if h_next > 0 and h_next % 3 == 0:
                            is_valid = True
                    
                    if is_valid and next_time not in meilleurs_gribs_par_heure:
                        date_str = date_heure_run.strftime('%Y%m%d')
                        run_str = f"{heure_run:02}z"
                        tranche_h_str = f"{h_next:03}"
                        reference_grib = f"{date_str}:{run_str}:{tranche_h_str}"
                        result.append(reference_grib)
                        logging.info(f"Added additional GRIB {reference_grib} to ensure 2+ timestamps")
                        break
                if len(result) >= 2:
                    break
    
    return result


def find_ifs_gribs_for_interpolation(date_cible: datetime, intervalle_h: int = 6) -> List[IFSRef]:
    """Find IFS run/forecast slices required for temporal interpolation.

    Returns a list of dict entries with keys:
    - run_datetime (UTC datetime)
    - run_hour (int)
    - fxx (int)
    - product ("oper" or "scda")
    - valid_time (UTC datetime)
    """

    if date_cible.tzinfo is None or date_cible.tzinfo.utcoffset(date_cible) is None:
        date_cible_utc = date_cible.replace(tzinfo=timezone.utc)
    else:
        date_cible_utc = date_cible.astimezone(timezone.utc)

    # IFS cadence is >= 3h, so bracket with a 3h guard band on each side.
    debut_periode_utc = date_cible_utc - timedelta(hours=3)
    fin_periode_utc = date_cible_utc + timedelta(hours=intervalle_h) + timedelta(hours=6)

    RUN_HEURES = [0, 6, 12, 18]
    DELAI_DISPONIBILITE_H = 7.5
    MAX_FORECAST_H = 360

    meilleurs_par_heure: Dict[datetime, IFSRef] = {}
    maintenant_utc = datetime.now(timezone.utc)

    date_max_run = fin_periode_utc - timedelta(hours=MAX_FORECAST_H)
    date_run_iter = datetime(
        date_max_run.year,
        date_max_run.month,
        date_max_run.day,
        tzinfo=timezone.utc,
    )

    while date_run_iter <= fin_periode_utc + timedelta(days=1):
        for heure_run in RUN_HEURES:
            date_heure_run = date_run_iter.replace(hour=heure_run)
            if date_heure_run + timedelta(hours=DELAI_DISPONIBILITE_H) > maintenant_utc:
                continue

            duration_h_min = (debut_periode_utc - date_heure_run).total_seconds() / 3600
            duration_h_max = (fin_periode_utc - date_heure_run).total_seconds() / 3600
            h_debut = max(0, math.floor(duration_h_min))
            h_fin = min(MAX_FORECAST_H, math.ceil(duration_h_max))

            for h in range(h_debut, h_fin + 1):
                if not _is_valid_ifs_fxx(heure_run, h):
                    continue
                valid_time = date_heure_run + timedelta(hours=h)
                meilleurs_par_heure[valid_time] = {
                    "run_datetime": date_heure_run,
                    "run_hour": heure_run,
                    "fxx": h,
                    "product": _ifs_product_for_run_hour(heure_run),
                    "valid_time": valid_time,
                }

        date_run_iter += timedelta(days=1)

    return [
        item[1]
        for item in sorted(meilleurs_par_heure.items(), key=lambda x: x[0])
    ]



def chkgribfile(file, model: str = "GFS"):
    """Check GRIB file validity.
    A valid file must exist, not be void, contain at least one grib message,
        and include required parameters.

        - GFS: u10, v10, gust are required.
        - IFS: u10 and v10 are required. Gust is optional for older files and
            can be reconstructed downstream from u10/v10 when unavailable.
    :param file:  path to check
    """
    logging.info(f"file to check: {file}")
    if not (file and os.path.exists(file) and os.path.getsize(file) > 0):
        logging.error(f"invalid file {file}: file does not exist or is empty")
        return False
    
    try:
        grbs = pygrib.open(file)  # type: ignore[attr-defined]
        n_values = int(grbs.messages)
        logging.info(f"{n_values} grib messages found")
        
        if n_values < 1:
            logging.error(f"invalid file {file}: file has no grib messages")
            grbs.close()
            return False
        
        # Check for required parameters by shortName
        model_upper = str(model).upper()
        if model_upper == "IFS":
            required_shortnames = {'10u', '10v'}
            gust_aliases = {'10fg', '10fg3'}
            required_labels = {'10u', '10v'}
            optional_labels = {'gust'}
        else:
            required_shortnames = {'10u', '10v', 'gust'}
            gust_aliases = set()
            required_labels = set(required_shortnames)
            optional_labels = set()
        found_shortnames = set()
        
        for grb in grbs:
            try:
                shortname = grb['shortName']
                name = grb['name']
                Unite = grb['units']
                Niveau = grb['level']
                param_id = getattr(grb, 'paramId', None)

                logging.info(f"shortname found : {shortname} - name: {name} - unit: {Unite} - level: {Niveau}")
                if shortname in required_shortnames:
                    found_shortnames.add(shortname)
                    logging.debug(f"Found required parameter: {shortname}")
                elif model_upper == "IFS" and (
                    shortname in gust_aliases
                    or param_id == 49
                    or (isinstance(name, str) and 'gust' in name.lower())
                ):
                    found_shortnames.add('gust')
                    logging.debug(
                        f"Found gust-like IFS parameter: shortName={shortname}, "
                        f"paramId={param_id}, name={name}"
                    )
            except Exception as e:
                logging.debug(f"Could not read shortName: {e}")
                continue
            
            # Early exit if all parameters found
            if found_shortnames == required_labels:
                break
        
        grbs.close()
        
        # Validate all required parameters are present
        missing_shortnames = required_labels - found_shortnames
        if missing_shortnames:
            logging.error(f"invalid file {file}: missing required parameters: {missing_shortnames}")
            return False

        missing_optional = optional_labels - found_shortnames
        if missing_optional:
            logging.warning(
                f"file {file}: optional parameters missing for {model_upper}: "
                f"{missing_optional} (fallback gust from u10/v10 will be used)"
            )
        
        present_labels = sorted(found_shortnames)
        logging.info(
            f"✓ File {file} is valid for {model_upper} "
            f"(required={sorted(required_labels)}, found={present_labels})"
        )
        return True
        
    except Exception as e:
        logging.error(f"Error validating file {file}: {e}")
        return False

# get a grib file tm: 
# parametre run et tranche horaire 
def getgfsgrib (savedir, run, tm ):
    """Download a GFS GRIB file using Herbie.
    The downloaded files are 0.25° subsets containing 10 m wind and gusts.
    """
    logging.info(f"Searching: {run} slice: {tm}")
    # Determine verbose behavior: only verbose when root logger is DEBUG
    verbose_flag = logging.getLogger().isEnabledFor(logging.DEBUG)
    FH = None
    essais = 0
    try:
        FH = HerbieWait(run, model="gfs", product="pgrb2.0p25", wait_for="20s", check_interval="5s", fxx=tm, save_dir=savedir, verbose=verbose_flag)
    except TimeoutError:
                logging.error("Herbie Wait exception: Timeout - file is not available")
                return (None)
    except Exception as error: 
                logging.error(f"Herbie Wait exception: Unexpected {error=}, {type(error)=}")
                return (None)      
    else :# normal exit from Herbie Wait a file could be downloaded 
        max_essais = 2
        gfile = None
        while essais < max_essais:
            try:
                gfile = FH.download(r":[UV]GRD:10 m above|GUST", verbose=verbose_flag)
            except Exception as err:
                essais += 1
                logging.error(f"Attempt {essais}/{max_essais} - Unexpected {err=}, {type(err)=}")
                if gfile and os.path.exists(gfile):
                    os.remove(gfile)
                gfile = None
                if essais < max_essais:
                    time.sleep(60)
            else:  # no error on FH download but test the file
                essais += 1
                # test if file exists
                if not (chkgribfile(gfile, model="GFS")):  # file is invalid
                    logging.error(f"Downloaded file failed validation: {gfile}")
                    if gfile and os.path.exists(gfile):
                        os.remove(gfile)
                    gfile = None
                    if essais < max_essais:
                        time.sleep(60)
                else:  # file is valid
                    logging.info(f"Downloaded file is valid: {gfile}")
                    break
        del FH
        if gfile is None:
            logging.error("Download failed after 2 attempts")
        return(gfile)


def getifsgrib(savedir, run, tm, product):
    """Download an IFS GRIB file using Herbie.

    Uses model=ifs with dynamic product (oper/scda) and explicit priority.
    """
    logging.info(f"Searching IFS: run={run} slice={tm} product={product}")
    verbose_flag = logging.getLogger().isEnabledFor(logging.DEBUG)
    FH = None
    essais = 0
    if run.tzinfo is not None and run.tzinfo.utcoffset(run) is not None:
        run_for_herbie = run.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        run_for_herbie = run

    try:
        FH = HerbieWait(
            run_for_herbie,
            model="ifs",
            product=product,
            priority=IFS_PRIORITY,
            wait_for="20s",
            check_interval="5s",
            fxx=tm,
            save_dir=savedir,
            verbose=verbose_flag,
        )
    except TimeoutError:
        logging.error("Herbie Wait exception: Timeout - IFS file is not available")
        return None
    except Exception as error:
        logging.error(f"Herbie Wait exception: Unexpected {error=}, {type(error)=}")
        return None
    else:
        max_essais = 2
        gfile = None
        while essais < max_essais:
            try:
                gfile = FH.download(":10u|10v|10fg|10fg3:", verbose=verbose_flag)
            except Exception as err:
                essais += 1
                logging.error(f"Attempt {essais}/{max_essais} - Unexpected {err=}, {type(err)=}")
                if gfile and os.path.exists(gfile):
                    os.remove(gfile)
                gfile = None
                if essais < max_essais:
                    time.sleep(60)
            else:
                essais += 1
                if not chkgribfile(gfile, model="IFS"):
                    logging.error(f"Downloaded IFS file failed validation: {gfile}")
                    if gfile and os.path.exists(gfile):
                        os.remove(gfile)
                    gfile = None
                    if essais < max_essais:
                        time.sleep(60)
                else:
                    logging.info(f"Downloaded IFS file is valid: {gfile}")
                    break
        del FH
        if gfile is None:
            logging.error("IFS download failed after 2 attempts")
        return gfile



def build_grib_list(hdir, date_cible: datetime, pas: Literal[1, 3] = 1, intervalle_h: int = 6, 
                    model: str = "GFS", resolution: float = 0.25, grib_limit: tuple = (0.0, 359.75, -90.0, 90.0)) -> List[str]:
    """
    Build a list of GRIB files required for temporal interpolation covering a ride/route.
    
    :param hdir: Base directory containing GRIB files (e.g., "/path/to/grib/data/")
    :param date_cible: Target datetime (departure time) - will be converted to UTC if needed
    :param pas: Time step granularity (1 = hourly, 3 = 3-hourly). Default: 1
    :param intervalle_h: Estimated duration of the ride/route in hours. Default: 6
                        Note: An automatic margin is added to ensure interpolation works
                        throughout the entire period (no need to manually add extra time).
    :param model: Weather model (default: "GFS")
    :param resolution: Grid resolution in degrees (default: 0.25)
    :param grib_limit: Tuple (lon_min, lon_max, lat_min, lat_max) for regional subsetting (not fully implemented)
    :return: List of absolute paths to GRIB files needed for the period
    
    Example:
        # For a 2-hour bike ride starting at 10:00 local time
        departure = datetime(2026, 2, 18, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))
        gribs = build_grib_list("/data/grib/", departure, pas=3, intervalle_h=2)
        # Returns files covering before, during, and after the ride for interpolation
    """

    model_upper = str(model).upper()

    gribliste = []

    if model_upper == "GFS":
        gribsfound = find_gribs_for_interpolation(date_cible, pas, intervalle_h)
        PATTERN1 = 'subset_*_gfs.t'
        PATTERN2 = 'z.pgrb2.0p25.f'
        PATHGRIB = os.path.join(hdir, 'gfs') + '/'

        for ref in gribsfound:
            refdate = (ref.split(':')[0])[0:27]
            refrun = (ref.split(':')[1])[0:2]
            refdaterun = datetime.strptime(refdate, "%Y%m%d") + timedelta(hours=int(refrun))
            reftm = (ref.split(':')[2])[0:3]
            fpattern = PATTERN1 + refrun + PATTERN2 + reftm
            path = PATHGRIB + refdate + "/"
            pathfile = path + fpattern
            resglob = glob.glob(pathfile)

            if (os.path.exists(path)) and (resglob):
                if chkgribfile(resglob[0], model="GFS"):
                    logging.info(f"file {resglob[0]} found and validated!")
                    gribliste.append(resglob[0])
                else:
                    logging.warning(f"Local file {resglob[0]} is invalid - removing and downloading...")
                    try:
                        os.remove(resglob[0])
                    except Exception as e:
                        logging.error(f"Failed to remove invalid file {resglob[0]}: {e}")

                    gfile = getgfsgrib(hdir, refdaterun, int(reftm))
                    if gfile:
                        gribliste.append(gfile)
                        logging.info(f"file {gfile} downloaded!")
                    else:
                        logging.info("Trying to download the previous run file...")
                        prevdaterun = refdaterun - timedelta(hours=6)
                        iprevtm = int(reftm) + 6
                        if iprevtm < 384:
                            if iprevtm > 120 and iprevtm % 3 != 0:
                                iprevtm = iprevtm + (3 - (iprevtm % 3))
                            gfile = getgfsgrib(hdir, prevdaterun, iprevtm)
                            if gfile:
                                gribliste.append(gfile)
                                logging.info(f"file {gfile} (previous run) downloaded!")
                            else:
                                logging.error("Previous run file could not be downloaded!")
                        else:
                            logging.warning("Previous grib out of range - change time or interval!")
            else:
                gfile = getgfsgrib(hdir, refdaterun, int(reftm))
                if gfile:
                    gribliste.append(gfile)
                    logging.info(f"file {gfile} downloaded!")
                else:
                    logging.info("Trying to download the previous run file...")
                    prevdaterun = refdaterun - timedelta(hours=6)
                    iprevtm = int(reftm) + 6
                    if iprevtm < 384:
                        if iprevtm > 120 and iprevtm % 3 != 0:
                            iprevtm = iprevtm + (3 - (iprevtm % 3))
                        gfile = getgfsgrib(hdir, prevdaterun, iprevtm)
                        if gfile:
                            gribliste.append(gfile)
                            logging.info(f"file {gfile} (previous run) downloaded!")
                        else:
                            logging.error("Previous run file could not be downloaded!")
                    else:
                        logging.warning("Previous grib out of range - change time or interval!")

        return gribliste

    if model_upper == "IFS":
        if pas not in (1, 3):
            raise ValueError("Le paramètre 'pas' doit valoir 1 ou 3")
        if pas == 1:
            logging.info("IFS data cadence is >=3h; pas=1 accepted but effective availability remains 3h/6h.")

        ifs_refs = find_ifs_gribs_for_interpolation(date_cible, intervalle_h)
        pathgrib = os.path.join(hdir, 'ifs')

        for entry in ifs_refs:
            run_dt = entry["run_datetime"]
            run_hour = int(entry["run_hour"])
            fxx = int(entry["fxx"])
            product = str(entry["product"])

            refdate = run_dt.strftime("%Y%m%d")
            run_stamp = run_dt.strftime("%Y%m%d%H0000")
            day_path = os.path.join(pathgrib, refdate)
            pattern = f"subset_*__{run_stamp}-{fxx}h-{product}-fc.grib2"
            resglob = glob.glob(os.path.join(day_path, pattern))

            if os.path.exists(day_path) and resglob:
                candidate = resglob[0]
                if chkgribfile(candidate, model="IFS"):
                    logging.info(f"file {candidate} found and validated!")
                    gribliste.append(candidate)
                    continue

                logging.warning(f"Local IFS file {candidate} is invalid - removing and downloading...")
                try:
                    os.remove(candidate)
                except Exception as e:
                    logging.error(f"Failed to remove invalid file {candidate}: {e}")

            gfile = getifsgrib(hdir, run_dt, fxx, product)
            if gfile:
                gribliste.append(gfile)
                logging.info(f"file {gfile} downloaded!")
                continue

            # fallback previous run (6h earlier)
            logging.info("Trying to download the previous IFS run file...")
            prev_run = run_dt - timedelta(hours=6)
            prev_fxx = fxx + 6
            prev_hour = prev_run.hour
            if _is_valid_ifs_fxx(prev_hour, prev_fxx):
                prev_product = _ifs_product_for_run_hour(prev_hour)
                gfile = getifsgrib(hdir, prev_run, prev_fxx, prev_product)
                if gfile:
                    gribliste.append(gfile)
                    logging.info(f"file {gfile} (previous run) downloaded!")
                else:
                    logging.error("Previous IFS run file could not be downloaded!")
            else:
                logging.warning("Previous IFS grib out of range - change time or interval!")

        return gribliste

    raise ValueError(f"Unsupported model '{model}'. Supported values: 'GFS', 'IFS'.")
         
# --- DEBUG ---
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logging.info("=== DEBUG MODE ===")
    
    # Configuration chemin
    if os.name == 'posix':
        hdir = "/mnt/nasdocker/grib/data/"
    else:
        hdir = "G:/grib/data/"
    mypas=1
   
    logging.info(f"[DEBUG] hdir: {hdir}")
    
    # Test 1: find_gribs_for_interpolation
    logging.info("[TEST 1] Call to find_gribs_for_interpolation()")
    date_exemple = datetime(2026, 1, 2, 8, 14, 0, tzinfo=timezone.utc)
    intervalle_exemple = 8
    
    logging.info(f"  Date: {date_exemple}")
    logging.info(f"  Interval: {intervalle_exemple}h")
    """"
    try:
        gribs_references = find_gribs_for_interpolation(date_exemple, mypas, intervalle_exemple)
        logging.info(f"  ✓ Result: {len(gribs_references)} references found")
        for ref in gribs_references:  
            logging.info(f"    - {ref}")
    except Exception as e:
        logging.error(f"  ✗ Error: {e}")
    """
    # Test 2: build_grib_list
    logging.info("[TEST 2] Call to build_grib_list()")
    try:
        gribs_list = build_grib_list(hdir, date_exemple, mypas,  intervalle_exemple)
        logging.info(f"  ✓ Result: {len(gribs_list)} files found/downloaded")
        for gfile in gribs_list:
            logging.info(f"    - {gfile}")
    except Exception as e:
        logging.error(f"  ✗ Error: {e}")
    
    logging.info("=== END DEBUG ===")
    
    