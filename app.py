from .ui.ui_form import Ui_MainWindow
from toolbox.qt import qtbase_future as qtbase
# from toolbox.qt import qtbase as qtbase
from . import q_appcfg, logger
import zipfile
import os


class PackerApp(qtbase.QApp):
    is_quit_confirm = 0
    
    def __init__(self, parent = None):
        super().__init__(Ui_MainWindow(), parent=parent)

    def init_after(self):
        self.set_main_app(appcfg=q_appcfg)
        self.set_logger(logger=logger)
        # ✅ 让窗口本身获得焦点（接收键盘事件）
        self.setFocusPolicy(qtbase.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        ui = self.ui


def main():
    print("-"*50)
    print(f"q_appcfg={q_appcfg}")
    print("-"*50)
    
    import sys
    qapp = qtbase.QApplication(sys.argv)
    # 设置全局默认字体
    qapp.setFont(qtbase.QFont("微软雅黑", 11))
    mapp = PackerApp()
    mapp.show()
    # 不生效，会被抢占焦点
    # mapp.raise_()          # 提升窗口到最上层
    # mapp.activateWindow()  # 请求激活该窗口
    sys.exit(qapp.exec())
