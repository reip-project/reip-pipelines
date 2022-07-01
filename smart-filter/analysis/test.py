import numpy as np
from pytz import timezone
from datetime import datetime, timedelta
from subprocess import Popen, PIPE
import pandas as pd
import tarfile
import glob
import os


def gini(array):
    """Calculate the Gini coefficient of a numpy array."""
    # based on bottom eq: http://www.statsdirect.com/help/content/image/stat0206_wmf.gif
    # from: http://www.statsdirect.com/help/default.htm#nonparametric_methods/gini.htm
    array = array[~np.isnan(array)]

    if len(array) == 0:
        return np.NaN
    array = array.values.flatten()  # all values are treated equally, arrays must be 1d
    if np.amin(array) < 0:
        array -= np.amin(array)  # values cannot be negative
    array += 0.0000001  # values cannot be 0
    array = np.sort(array)  # values must be sorted
    index = np.arange(1, array.shape[0] + 1)  # index per array element
    n = array.shape[0]  # number of array elements
    return ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))  # Gini coefficient


def calc_leq(data):
    return 10 * np.log10(np.mean(10 ** (data / 10)))


def calcl90(data):
    stat_percentile = 100 - 90
    return np.nanpercentile(data, stat_percentile)


def calcl10(data):
    stat_percentile = 100 - 10
    return np.nanpercentile(data, stat_percentile)


def calcl5(data):
    stat_percentile = 100 - 5
    return np.nanpercentile(data, stat_percentile)


def calcl1(data):
    stat_percentile = 100 - 1
    return np.nanpercentile(data, stat_percentile)


def is_fault_day(cur_day, fault_st, fault_en):
    if isinstance(fault_st, str) and isinstance(fault_en, str):
        fault_st_dt = timezone('America/New_York').localize(datetime.strptime(fault_st, '%Y-%m-%d'))
        fault_en_dt = timezone('America/New_York').localize(datetime.strptime(fault_en, '%Y-%m-%d'))
        if fault_st_dt.date() <= cur_day.date() <= fault_en_dt.date():
            return True
        else:
            return False
    else:
        return False


def localize_timestamps(_df, ts_column='ts'):
    ts_vals = _df[ts_column].values.astype(np.float64) * 1000
    _df['time'] = np.asarray(ts_vals, dtype='datetime64[ms]')
    _df['time'] = _df['time'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
    _df.set_index(pd.DatetimeIndex(_df['time']), inplace=True)
    _df['weekday'] = _df.index.weekday
    _df['min_of_day'] = (_df.index.hour * 60.0) + _df.index.minute
    _df['hour_of_day'] = _df.index.hour
    _df['day_of_year'] = _df.index.dayofyear
    _df['date'] = _df.index.date
    return _df


def parse_minute_tar(min_tar_file_obj):
    try:
        min_tar_obj = tarfile.open(fileobj=min_tar_file_obj, mode='r|*')

        for csv_tar_obj in min_tar_obj:
            csv_name = csv_tar_obj.name
            if 'slow' in csv_name:
                continue
            csv_file_obj = min_tar_obj.extractfile(csv_tar_obj)

            csv_df = pd.read_csv(csv_file_obj,
                                 usecols=[0, 2],
                                 sep=',',
                                 header=0,
                                 names=['ts', 'dba'],
                                 dtype={'ts': np.float64, 'dba': np.float64})
    except Exception as e:
        print('ERROR: Couldnt read minute tar file, continuing')
        print(e)
        return pd.DataFrame()

    return csv_df


def drop_misplaced_data(_df, keep_date):
    return _df[_df['date'] == keep_date]


def process_df(_df, day_date_obj=None, ts_column='ts'):
    _day_df = _df.drop_duplicates(subset=[ts_column])
    _day_df = _day_df.sort_values(by=[ts_column])
    _day_df = localize_timestamps(_day_df.copy())
    _day_df = drop_misplaced_data(_day_df.copy(), day_date_obj)

    return _day_df


def parse_day_dir(dir_path):
    _day_df = pd.DataFrame()

    for min_tar_path in glob.glob('%s/*.tar' % dir_path):
        tar_fname = os.path.basename(min_tar_path)
        min_tar_ts = float(tar_fname.split('_')[1])

        min_tar_local_dt = timezone('America/New_York').localize(datetime.fromtimestamp(min_tar_ts))

        # Skip tar file if its not part of this day
        if str(min_tar_local_dt.date()) not in min_tar_path:
            continue

        with open(min_tar_path, 'rb') as min_tar_file_obj:
            min_df = parse_minute_tar(min_tar_file_obj)

        _day_df = pd.concat([_day_df, min_df])
    return _day_df


def parse_day_tar(tar_path):
    try:
        day_tar_obj = tarfile.open(tar_path, mode='r|*')
        _day_df = pd.DataFrame()
        for min_tar_obj in day_tar_obj:
            min_tar_name = min_tar_obj.name
            if min_tar_name == '.':
                continue
            min_tar_ts = float(min_tar_name.split('_')[1])
            min_tar_local_dt = timezone('America/New_York').localize(datetime.fromtimestamp(min_tar_ts))

            # Skip tar file if its not part of this day
            if str(min_tar_local_dt.date()) not in tar_path:
                continue
            min_tar_file_obj = day_tar_obj.extractfile(min_tar_obj)

            min_df = parse_minute_tar(min_tar_file_obj)
            _day_df = pd.concat([_day_df, min_df])

    except Exception as e:
        print('ERROR: Couldnt read day tar file, continuing')
        print(e)
        return pd.DataFrame()
    return _day_df


def upload_to_drive(f_path):
    process = Popen(
        ['/usr/bin/rclone', 'copy', f_path, 'gdrive_covid_spl:/SONYC-RESTRICTED/covid_spl/', '--bwlimit', '1024k'],
        stdout=PIPE)
    (output, err) = process.communicate()
    exit_code = process.wait()
    return exit_code


def get_uploaded_list():
    process = Popen(['/usr/bin/rclone', 'ls', '--max-depth', '1', 'gdrive_covid_spl:/SONYC-RESTRICTED/covid_spl/'],
                    stdout=PIPE)
    (output, err) = process.communicate()

    file_lines = [x.strip().split() for x in output.splitlines()]

    remote_file_list = []

    for line in file_lines:
        if int(line[0]) > 5000:
            remote_file_list.append(line[1].decode('utf-8'))

    exit_code = process.wait()

    if exit_code == 0:
        return remote_file_list
    else:
        return False


def add_node_meta(_df, meta_row):
    meta_row.replace({None: False, 1: True}, inplace=True)
    meta_columns = meta_row.index[2:-2]
    _df = pd.concat([_df, pd.DataFrame(columns=meta_columns)], sort=True)

    for col in meta_columns:
        _df[col] = meta_row[col]

    return _df


def add_weather_data(_df, day_date_obj=None, agg_hour=1):
    next_day_date_obj = day_date_obj + timedelta(days=1)

    # https://mesonet.agron.iastate.edu/request/download.phtml?network=NY_ASOS
    weather_url = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?' \
                  'station=JFK' \
                  '&tz=America%2FNew_York' \
                  '&data=tmpc&data=dwpc&data=relh&data=drct&data=sped&data=mslp&data=p01m&data=vsby&data=gust_mph&data=peak_wind_gust_mph' \
                  '&year1=' + str(day_date_obj.year) + '&month1=' + str(day_date_obj.month) + '&day1=' + str(
        day_date_obj.day) + \
                  '&year2=' + str(next_day_date_obj.year) + '&month2=' + str(next_day_date_obj.month) + '&day2=' + str(
        next_day_date_obj.day) + \
                  '&format=onlycomma' \
                  '&latlon=no' \
                  '&missing=empty' \
                  '&trace=empty' \
                  '&direct=no' \
                  '&report_type=1' \
                  '&report_type=2'

    w_df = pd.read_csv(weather_url)
    w_df = w_df[pd.notnull(w_df['tmpc'])]

    w_df['datetime'] = pd.to_datetime(w_df['valid'], format='%Y-%m-%d %H:%M', errors='ignore')
    w_df['datetime'] = w_df['datetime'].dt.tz_localize('US/Eastern', ambiguous='infer')

    drop_arr = []
    for index, row in w_df.iterrows():
        if row['datetime'].minute != 51:
            drop_arr.append(index)
        else:
            w_df.at[index, 'datetime'] = row['datetime'] - timedelta(minutes=51)

    w_df.drop(drop_arr, inplace=True)
    w_df.drop(columns=['station', 'valid'], inplace=True)
    w_df.rename(columns={'p01m': 'precipitation_mm',
                         'sped': 'wind_speed_mph',
                         'relh': 'rh_percentage',
                         'tmpc': 'temp_celcius',
                         'dwpc': 'dewp_celcius',
                         'drct': 'wind_dir',
                         'mslp': 'sea_level_pressure_mb',
                         'vsby': 'visibility_miles'
                         }, inplace=True)

    w_df.set_index('datetime', inplace=True, drop=True)

    return _df.merge(w_df, left_on='time', right_on='datetime')


def add_meta_columns(main_df_for_meta):
    meta_df = pd.read_csv('node_meta_full.csv', encoding='utf-8')
    meta_df.replace({None: False, 1: True}, inplace=True)
    meta_columns = meta_df.columns[1:-1]
    main_df_for_meta = pd.concat([main_df_for_meta, pd.DataFrame(columns=meta_columns)], sort=True)

    for index, row in main_df_for_meta.iterrows():
        meta_dfrow = meta_df[meta_df['node_id'] == row['sensor_id']]
        main_df_for_meta.at[index, meta_columns] = meta_dfrow[meta_columns].values[0]

    return main_df_for_meta


def cleanup_df(_df):
    return _df.round(6)
