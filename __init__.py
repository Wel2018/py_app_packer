"""Python App Packer"""

from toolbox.qt import qtbase
from .version import __version__
from .version import __update_timestamp__


q_appcfg = qtbase.QAppConfig(
    name = "Python 应用打包器",
    name_en = "Python App Packer",
    date=__update_timestamp__,
    version = __version__,
    fontsize = 11,
    slot="py_app_packer",
    APPCFG_DICT=qtbase.get_appcfg(__file__),
    FF=__file__,
)

ROOT = q_appcfg.ROOT
