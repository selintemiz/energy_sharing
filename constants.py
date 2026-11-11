from os.path import join

### Default Input Filenames  ###

PV_FILE = 'pv.csv'
BAT_FILE = 'battery.csv'
AVG_FILE = 'avg.csv'
CONS_FILE = 'cons.csv'

SUN_FILE = 'sun.csv'
PRICE_FILE = 'price.csv'

### Default Directories and Filepaths  ###

DATA_FOLDER = join('..', 'data')
DATA_FOLDER_2221 = join(DATA_FOLDER, 'data_2221')
DEFAULT_FOLDER = join(DATA_FOLDER, 'data_100')

PV_PROFILES_FILE = join(DATA_FOLDER, 'pv_profiles_extract.csv')
PV_PROFILES_FULL_FILE = join(DATA_FOLDER, 'pv_profiles.csv')

SUN_FILE_DEFAULT = join(DATA_FOLDER, SUN_FILE)
PRICE_FILE_DEFAULT = join(DATA_FOLDER, PRICE_FILE)
PV_PROFILES_DEFAULT = join(DATA_FOLDER, PV_PROFILES_FILE)

PV_FILE_DEFAULT = join(DEFAULT_FOLDER, PV_FILE)
BAT_FILE_DEFAULT = join(DEFAULT_FOLDER, BAT_FILE)
AVG_FILE_DEFAULT = join(DEFAULT_FOLDER, AVG_FILE)
CONS_FILE_DEFAULT = join(DEFAULT_FOLDER, CONS_FILE)

DATA_FOLDER_SCE13 = join(DATA_FOLDER, 'data_scenario_13')

# Additions for extended optimizer

REGION_FILE = join(DATA_FOLDER_2221, 'households3.csv')

ORIENTATION_FILE = join(DATA_FOLDER_2221, 'orientations.csv')
PRICE_REGION_FILE_DEFAULT = join(DATA_FOLDER, 'prices2020_4regions.csv')

INDIVIDUAL_SUN_FILE = join(DATA_FOLDER_2221, 'sunprofiles.csv')
INDIVIDUAL_PRICE_FILE = join(DATA_FOLDER_2221, 'prices.csv')

PV_2221_FILE = join(DATA_FOLDER_2221, PV_FILE)
BAT_2221_FILE = join(DATA_FOLDER_2221, BAT_FILE)
AVG_2221_FILE = join(DATA_FOLDER_2221, AVG_FILE)
CONS_2221_FILE = join(DATA_FOLDER_2221, CONS_FILE)

# Additions for serialized binary content

BIN_FOLDER = 'bin'
OPT_EXT_FILE = join(BIN_FOLDER, "opt_ext.bin")
HOUSEHOLDS_BINDUMP = join(BIN_FOLDER, "households.bin")
OPT_2221_BIN = join(BIN_FOLDER, 'opt2221.bin')
OPT_2221_BIN_EXT = join(DATA_FOLDER_2221, 'opt2221ext.bin')

### Default Values  ###

# Default tax values (25% tax, taxes in €/kWh)

TAX_DEFAULT = 1.25
EL_TAX_DEFAULT = 0.069066
EL_NET_DEFAULT = 0.0057555

DEFAULT_LP_SOLVER = 'cbc'
