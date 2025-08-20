
from dynaconf import Dynaconf
settings = Dynaconf(envvar_prefix="DYNACONF", settings_files=['settings.yaml', '.secrets.yaml'])
import pdb; pdb.set_trace()
settings.setenv('default')

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
