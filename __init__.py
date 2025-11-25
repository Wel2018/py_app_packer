"""Python App Packer"""

from toolbox.qt import qtbase
from toolbox.core.logbase import get_logger


q_appcfg = qtbase.QAppConfig(
    name = "Python 应用打包器",
    name_en = "Python App Packer",
    date="2025-11-25",
    version = "1.0.0",
    fontsize = 13,
    slot="py_app_packer",
    APPCFG_DICT=qtbase.get_appcfg(__file__),
    FF=__file__,
)

logger = get_logger(q_appcfg.slot)
ROOT = q_appcfg.ROOT
