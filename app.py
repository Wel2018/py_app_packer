import sys
from .ui.ui_form import Ui_MainWindow
from toolbox.qt import qtbase_future as qtbase
from toolbox.core.log import LogHelper, printc
from . import q_appcfg
from loguru import logger
from PySide6 import QtWidgets
from datetime import date, datetime
import os
import shutil


class PackerApp(qtbase.QApp):
    is_quit_confirm = 0

    def __init__(self, parent=None):
        super().__init__(Ui_MainWindow(), parent=parent)
        self.ui: Ui_MainWindow

    def init_after(self):
        self.set_main_app(appcfg=q_appcfg, is_set_theme=0)
        self.set_logger(logger=logger)
        # ✅ 让窗口本身获得焦点（接收键盘事件）
        self.setFocusPolicy(qtbase.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        ui = self.ui

        qtbase.bind_clicked(ui.btn_scan, self.on_scan)
        qtbase.bind_clicked(ui.btn_root_select, self.on_root_select)
        qtbase.bind_clicked(ui.btn_update_version, self.on_update_version)
        qtbase.bind_clicked(ui.btn_update_major, self.on_bump_major)
        qtbase.bind_clicked(ui.btn_update_minor, self.on_bump_minor)
        qtbase.bind_clicked(ui.btn_update_patch, self.on_bump_patch)
        qtbase.bind_clicked(ui.btn_release, self.on_release)
        qtbase.bind_clicked(ui.btn_zip, self.on_zip)
        qtbase.bind_clicked(ui.btn_open_dist_dir, self.on_open_dist_dir)

        # 配置模块列表表头（包名 / 路径 / 完整版本号 / 更新时间），路径列隐藏，仅内部使用
        table = ui.table_mod
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["包名", "路径", "版本号", "更新时间"])
        header = table.horizontalHeader()
        # 第一列（包名）按内容自适应宽度，第三列（版本号）按内容，第四列（更新时间）占用剩余空间
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.setColumnHidden(1, True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.itemSelectionChanged.connect(self.on_mod_selected)

        self.ui.btn_scan.click()

    def _scan_packages(self, root_path: str):
        """扫描 root_path 下所有包含 __init__.py 和 __main__.py 的包"""
        packages: list[tuple[str, str]] = []
        root_path = os.path.abspath(root_path)

        for dirpath, _, filenames in os.walk(root_path):
            if "__init__.py" in filenames and "__main__.py" in filenames:
                rel = os.path.relpath(dirpath, root_path)
                if rel == ".":
                    pkg_name = os.path.basename(root_path)
                else:
                    pkg_name = rel.replace(os.sep, ".")
                packages.append((pkg_name, dirpath))

        return packages

    # ---------- 版本号工具函数 ----------

    # ---------- 模块选择 & 版本读取 ----------
    def _get_selected_row(self):
        """返回当前选中行索引，未选中则返回 -1"""
        table = self.ui.table_mod
        sel_model = table.selectionModel()
        if not sel_model:
            return -1
        rows = sel_model.selectedRows()
        if not rows:
            return -1
        return rows[0].row()

    def _get_row_info(self, row: int):
        """根据行号获取 (包名, 路径)，任一为空则返回 (None, None)"""
        table = self.ui.table_mod
        name_item = table.item(row, 0)
        path_item = table.item(row, 1)
        if not name_item or not path_item:
            return None, None
        pkg_name = name_item.text().strip()
        pkg_path = path_item.text().strip()
        if not pkg_name or not pkg_path:
            return None, None
        return pkg_name, pkg_path

    def _version_file_path(self, pkg_path: str) -> str:
        return os.path.join(pkg_path, "version.py")

    def _read_version_from_file(self, version_file: str):
        """兼容旧接口：仅返回 __version__，失败返回 None"""
        v, _ = self._read_version_info(version_file)
        return v

    def _read_version_info(self, version_file: str) -> tuple[str | None, str | None]:
        """从 version.py 中读取 (__version__, __update_timestamp__)，任一不存在则为 None"""
        if not os.path.isfile(version_file):
            return None, None
        try:
            ns: dict = {}
            with open(version_file, "r", encoding="utf-8") as f:
                code = f.read()
            exec(code, ns)
            v = ns.get("__version__")
            ts = ns.get("__update_timestamp__")
            return (str(v) if v is not None else None,
                    str(ts) if ts is not None else None)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"读取版本文件失败: {version_file}, err={e}")
            return None, None

    def _default_version(self) -> str:
        today = date.today().strftime("%Y%m%d")
        return f"0.0.1.post{today}"

    def _split_version(self, full_version: str) -> tuple[str, str]:
        """拆分完整版本号为 (主版本, 后缀)，如 0.1.6.post20260114 -> ('0.1.6', '20260114')"""
        if not full_version:
            return "", ""
        parts = full_version.split(".post", 1)
        base = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""
        return base, suffix

    def _write_version_file(self, version_file: str, full_version: str) -> str:
        """写入 version.py，包含版本号和更新时间，返回写入的时间戳字符串"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(version_file), exist_ok=True)
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(f'__version__ = "{full_version}"\n')
            f.write(f'__update_timestamp__ = "{ts}"\n')
        return ts

    def _ensure_version(self, pkg_path: str) -> str:
        """获取包的完整版本号，如不存在则按默认规则创建 version.py 并返回"""
        version_file = self._version_file_path(pkg_path)
        full_version, _ = self._read_version_info(version_file)
        if full_version is not None:
            return full_version
        # 不存在时自动创建默认版本文件
        full_version = self._default_version()
        try:
            self._write_version_file(version_file, full_version)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"创建默认版本文件失败: {version_file}, err={e}")
        return full_version

    def on_mod_selected(self):
        """当选择表格中的某一行时，在右侧显示包名、路径和版本号"""
        ui = self.ui
        row = self._get_selected_row()
        if row < 0:
            return

        pkg_name, pkg_path = self._get_row_info(row)
        if not pkg_name or not pkg_path:
            return

        ui.mod_name.setText(pkg_name)
        ui.mod_path.setText(pkg_path)

        # 确保有版本文件并读取完整版本号与更新时间
        full_version = self._ensure_version(pkg_path)
        _, ts = self._read_version_info(self._version_file_path(pkg_path))
        base_version, _ = self._split_version(full_version)
        ui.mod_version.setText(base_version)

        # 更新表格中对应行的“版本号”列
        table = ui.table_mod
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(full_version))
        table.setItem(row, 3, QtWidgets.QTableWidgetItem(ts or ""))

    def on_scan(self):
        ui = self.ui
        root_path = ui.root_path.text().strip()
        if not root_path:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择项目根路径。")
            return
        if not os.path.isdir(root_path):
            QtWidgets.QMessageBox.warning(self, "错误", f"路径不存在或不是文件夹：\n{root_path}")
            return

        packages = self._scan_packages(root_path)

        table = ui.table_mod
        table.setRowCount(0)

        for row, (pkg_name, pkg_path) in enumerate(packages):
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(pkg_name))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(pkg_path))

            # 尝试读取现有版本信息（不在这里强制创建文件）
            version_file = self._version_file_path(pkg_path)
            full_version, ts = self._read_version_info(version_file)
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(full_version or ""))
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(ts or ""))

        ui.statusbar.showMessage(f"共找到 {len(packages)} 个可打包模块。", 5000)
        ui.mod_name.clear()
        ui.mod_version.clear()
        ui.mod_path.clear()

    # ---------- 版本号自增（major / minor / patch） ----------
    def _parse_base_version(self, base_version: str) -> tuple[int, int, int]:
        """
        将 '0.1.6' 解析为 (0, 1, 6)，非法则返回 (0, 0, 0)
        """
        parts = base_version.strip().split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            return 0, 0, 0
        return int(parts[0]), int(parts[1]), int(parts[2])

    def _set_base_version(self, major: int, minor: int, patch: int):
        """
        将 (major, minor, patch) 回写到 mod_version 中（不带 .post）
        """
        self.ui.mod_version.setText(f"{major}.{minor}.{patch}")

    def _bump_version(self, part: str):
        """
        part: 'major' / 'minor' / 'patch'
        """
        base = self.ui.mod_version.text().strip()
        major, minor, patch = self._parse_base_version(base)

        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        elif part == "patch":
            patch += 1

        self._set_base_version(major, minor, patch)

    def on_bump_major(self):
        self._bump_version("major")

    def on_bump_minor(self):
        self._bump_version("minor")

    def on_bump_patch(self):
        self._bump_version("patch")

    def on_root_select(self):
        ui = self.ui
        current = ui.root_path.text().strip() or os.getcwd()
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "选择项目根路径", current)
        if not directory:
            return
        ui.root_path.setText(directory)

    # ---------- 运行加密逻辑（pyarmor + 依赖拷贝） ----------
    def on_release(self):
        """使用 pyarmor 加密：对所选模块执行等价于 encrypt.sh 的逻辑"""
        row = self._get_selected_row()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "提示", "请先在模块列表中选择一个包。")
            return

        pkg_name, pkg_path = self._get_row_info(row)
        if not pkg_name or not pkg_path:
            QtWidgets.QMessageBox.warning(self, "错误", "无法获取所选包信息。")
            return

        # TARGET 为项目名（如 realman_teleop）
        target = os.path.basename(pkg_path)

        # 仓库根目录（与示例脚本中相同，相对路径以此为基准）
        #repo_root = "" # q_appcfg.ROOT
        repo_root = os.path.abspath("D:\\wk\\Codehub\\0\\phimate")  # 改为你的 phimate 绝对路径

        # OUTPUT=dist/dist_${TARGET}_`date "+%Y-%m-%d-%H.%M.%S"`
        ts = datetime.now().strftime("%Y-%m-%d-%H.%M.%S")
        output_dir_name = f"dist_{target}_{ts}"
        output_root = os.path.join(repo_root, "dist", output_dir_name)
        input_path = os.path.normpath(os.path.join(repo_root, f"projects\\{target}"))  # 用 \\ 替代 /

        # 日志提示
        msg1 = f"加密模块 {target} 到输出目录 {output_root}"
        msg2 = "注：忽略 ERROR out of license，不影响程序运行"
        logger.info(msg1)
        logger.info(msg2)
        self.ui.statusbar.showMessage(msg1, 5000)


        # 4. 获取 pyarmor 的绝对路径（避免找不到可执行文件导致的路径错误）
        def get_pyarmor_exe():
            """获取 pyarmor 可执行文件的绝对路径"""
            pyarmor_exe = "pyarmor.exe" if sys.platform == "win32" else "pyarmor"
            # 优先从 Python 环境的 Scripts 目录找（uv/venv 环境）
            scripts_dir = os.path.join(sys.prefix, "Scripts")
            local_pyarmor = os.path.join(scripts_dir, pyarmor_exe)
            if os.path.exists(local_pyarmor):
                return local_pyarmor
            # 其次找系统 PATH 中的 pyarmor
            import shutil
            pyarmor_path = shutil.which(pyarmor_exe)
            if pyarmor_path:
                return pyarmor_path
            raise FileNotFoundError("未找到 pyarmor 可执行文件，请确认已安装：uv add pyarmor")


        # 1) 加密模块（pyarmor gen）
        try:
            import subprocess
            os.makedirs(output_root, exist_ok=True)
            pyarmor_path = get_pyarmor_exe()

            # 等价于：
            # pyarmor --silent gen -O ${OUTPUT} -r -i projects/${TARGET}
            logger.info("加密模块...")
            cmd = [
                # "pyarmor",
                pyarmor_path,
                "--silent",
                "gen",
                "-O",
                output_root,
                "-r",
                "-i",
                input_path
                # f"projects/{target}",
            ]
            logger.info(f"运行命令: {' '.join(cmd)}  (cwd={repo_root})")
            proc = subprocess.Popen(
                cmd,
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,  # Windows 下必须为 False
            )
            out, err = proc.communicate(timeout=300)  # 5分钟超时
            out = out or ""
            err = err or ""

            # 允许 out of license 错误继续后续流程
            if proc.returncode != 0:
                combined = (out + "\n" + err).lower()
                if "out of license" in combined:
                    logger.warning(
                        f"pyarmor 返回码 {proc.returncode}，但检测到 'out of license'，按脚本约定忽略。\n"
                        f"stdout:\n{out}\nstderr:\n{err}"
                    )
                else:
                    logger.error(
                        f"pyarmor 执行失败: 返回码 {proc.returncode}\nstdout:\n{out}\nstderr:\n{err}"
                    )
                    QtWidgets.QMessageBox.critical(
                        self,
                        "错误",
                        f"pyarmor 执行失败（退出码 {proc.returncode}）：\n{err}",
                    )
                    return
            else:
                logger.info(f"pyarmor 执行成功。\nstdout:\n{out}")

        except Exception as e:  # noqa: BLE001
            logger.exception(f"执行 pyarmor 过程异常: target={target}, err={e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"执行 pyarmor 过程异常：\n{e}",
            )
            return

        # 2) 拷贝配置文件
        try:
            logger.info("拷贝配置文件...")
            src_appcfg = os.path.join(repo_root, "projects", target, "appcfg.yaml")
            dst_target_root = os.path.join(output_root, target)
            os.makedirs(dst_target_root, exist_ok=True)
            if os.path.isfile(src_appcfg):
                shutil.copy2(src_appcfg, os.path.join(dst_target_root, "appcfg.yaml"))
            else:
                logger.warning(f"未找到配置文件: {src_appcfg}")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"拷贝配置文件失败: target={target}, err={e}")

        # 3) 拷贝机械臂依赖库：projects/${TARGET}/bgtask/common -> ${OUTPUT}/${TARGET}/bgtask/common
        # try:
        #     logger.info("拷贝机械臂依赖库...")
        #     src_common = os.path.join(repo_root, "projects", target, "bgtask", "common")
        #     dst_bgtask = os.path.join(output_root, target, "bgtask")
        #     dst_common = os.path.join(dst_bgtask, "common")
        #     if os.path.isdir(src_common):
        #         os.makedirs(dst_bgtask, exist_ok=True)
        #         # Python 3.8+ 支持 dirs_exist_ok
        #         shutil.copytree(src_common, dst_common, dirs_exist_ok=True)
        #     else:
        #         logger.warning(f"未找到机械臂依赖库目录: {src_common}")
        # except Exception as e:  # noqa: BLE001
        #     logger.exception(f"拷贝机械臂依赖库失败: target={target}, err={e}")
        
        # 3) 拷贝映射文件指定的内容（例如：bgtask/common、appcfg.yaml 等）
        try:
            logger.info("拷贝映射文件指定的内容...")
            mapp_path = os.path.join(repo_root, "projects", target, "mapp.txt")
            if not os.path.isfile(mapp_path):
                logger.warning(f"未找到 mapp.txt 映射文件：{mapp_path}")
            else:
                with open(mapp_path, "r", encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        # 跳过空行和注释行
                        if not line or line.startswith("#"):
                            continue

                        # 相对路径，如 'bgtask/common' 或 'appcfg.yaml'
                        rel_path = line.replace("\\", "/")
                        src_path = os.path.join(repo_root, "projects", target, rel_path)
                        dst_path = os.path.join(output_root, target, rel_path)

                        if os.path.isdir(src_path):
                            # 目录拷贝
                            logger.info(f"拷贝目录: {src_path} -> {dst_path}")
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                        elif os.path.isfile(src_path):
                            # 文件拷贝
                            logger.info(f"拷贝文件: {src_path} -> {dst_path}")
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copy2(src_path, dst_path)
                        else:
                            logger.warning(f"mapp.txt 中的路径不存在，已跳过: {src_path}")

        except Exception as e:  # noqa: BLE001
            logger.exception(f"拷贝映射文件指定的内容失败: target={target}, err={e}")

        # 4) 拷贝界面描述：projects/${TARGET}/ui -> ${OUTPUT}/${TARGET}/ui
        try:
            logger.info("拷贝界面描述...")
            src_ui = os.path.join(repo_root, "projects", target, "ui")
            dst_ui = os.path.join(output_root, target, "ui")
            if os.path.isdir(src_ui):
                shutil.copytree(src_ui, dst_ui, dirs_exist_ok=True)
            else:
                logger.warning(f"未找到界面描述目录: {src_ui}")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"拷贝界面描述失败: target={target}, err={e}")

        # 记录最近一次发布输出目录和目标名，供压缩使用
        self.last_output_root = output_root
        self.last_output_target = target

        # 完成提示
        done_msg = f"模块 {target} 加密完成！输出目录：\n{output_root}"
        logger.info(done_msg)
        QtWidgets.QMessageBox.information(self, "完成", done_msg)

    # ---------- 压缩发布包为 zip ----------
    def on_zip(self):
        """
        将最近一次 on_release 生成的发布目录压缩为 zip 文件
        """
        output_root = getattr(self, "last_output_root", None)
        target = getattr(self, "last_output_target", None)
        if not output_root or not target:
            QtWidgets.QMessageBox.warning(
                self,
                "提示",
                "请先点击“发布包”完成一次发布，再压缩发布包。",
            )
            return

        if not os.path.isdir(output_root):
            QtWidgets.QMessageBox.warning(
                self,
                "提示",
                f"发布目录不存在，无法压缩：\n{output_root}",
            )
            return

        # zip 文件放在 dist 目录下，名称类似 dist_TARGET_时间.zip
        repo_root = os.path.abspath("D:\\wk\\Codehub\\0\\phimate")  # 与 on_release 保持一致
        dist_dir = os.path.join(repo_root, "dist")
        os.makedirs(dist_dir, exist_ok=True)

        base_name = os.path.basename(output_root)  # dist_TARGET_YYYY-MM-DD-HH.MM.SS
        zip_path = os.path.join(dist_dir, base_name + ".zip")

        try:
            # 如果已存在同名 zip，先删除
            if os.path.exists(zip_path):
                os.remove(zip_path)

            import zipfile

            logger.info(f"开始压缩发布目录为 zip：{output_root} -> {zip_path}")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(output_root):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        # 计算在 zip 中的相对路径（相对于 output_root）
                        arcname = os.path.relpath(fpath, output_root)
                        zf.write(fpath, arcname)

            # 如果勾选了“压缩后删除文件夹”，则在压缩成功后删除源目录
            if self.ui.is_delete_zipped_folder.isChecked():
                logger.info(f"按勾选设置，压缩完成后删除源目录：{output_root}")
                shutil.rmtree(output_root, ignore_errors=False)

            msg = f"发布包已压缩为 zip：\n{zip_path}"
            logger.info(msg)
            QtWidgets.QMessageBox.information(self, "完成", msg)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"压缩发布包失败: dir={output_root}, err={e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"压缩发布包失败：\n{zip_path}\n\n{e}",
            )

    # ---------- 打开发布目录 ----------
    def on_open_dist_dir(self):
        """
        打开最近一次 on_release 生成的发布目录
        """
        output_root = getattr(self, "last_output_root", None)
        if not output_root:
            QtWidgets.QMessageBox.warning(
                self,
                "提示",
                "请先点击“发布包”完成一次发布，再打开发布目录。",
            )
            return

        if not os.path.isdir(output_root):
            QtWidgets.QMessageBox.warning(
                self,
                "提示",
                f"发布目录不存在：\n{output_root}",
            )
            return

        try:
            # Windows 使用 explorer，Linux/Mac 使用 xdg-open/open
            if sys.platform == "win32":
                os.startfile(output_root)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", output_root])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", output_root])
            logger.info(f"已打开发布目录：{output_root}")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"打开发布目录失败: dir={output_root}, err={e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"打开发布目录失败：\n{output_root}\n\n{e}",
            )

    # ---------- 更新版本号 ----------
    def on_update_version(self):
        ui = self.ui
        row = self._get_selected_row()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "提示", "请先在模块列表中选择一个包。")
            return

        pkg_name, pkg_path = self._get_row_info(row)
        if not pkg_name or not pkg_path:
            QtWidgets.QMessageBox.warning(self, "错误", "无法获取所选包信息。")
            return

        base_version = ui.mod_version.text().strip()
        if not base_version:
            QtWidgets.QMessageBox.warning(self, "提示", "版本号不能为空。")
            return

        today = date.today().strftime("%Y%m%d")
        full_version = f"{base_version}.post{today}"

        version_file = self._version_file_path(pkg_path)
        try:
            ts = self._write_version_file(version_file, full_version)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"写入版本文件失败: {version_file}, err={e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"写入版本文件失败：\n{version_file}\n\n{e}")
            return

        # 更新表格中该行的完整版本号与更新时间
        table = ui.table_mod
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(full_version))
        table.setItem(row, 3, QtWidgets.QTableWidgetItem(ts))

        msg = f"模块 {pkg_name} 的版本号已更新为 {full_version}"
        ui.statusbar.showMessage(msg, 5000)
        QtWidgets.QMessageBox.information(self, "完成", msg)


def main():
    LogHelper.init(q_appcfg.slot)
    printc(f"q_appcfg={q_appcfg}")
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
