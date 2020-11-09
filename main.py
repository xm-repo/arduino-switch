from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRect
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMainWindow, QLabel, QGridLayout, QWidget, QLineEdit
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QIODevice
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtNetwork import QTcpSocket

import os
import sys
import time
import json
import typing as tp

# while true ; do sudo nc -l 127.0.0.1 80 < test.txt; done

OUTPUTS_COUNT: int = 6
INPUTS_COUNT: int = 8

class PrettySwitch(QtWidgets.QPushButton):

    def __init__(self, parent = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(100)
        self.setMinimumHeight(22)
        self.changed = False
        self.toggled.connect(self.on_changed)

    def on_changed(self):
        self.changed = True

    def paintEvent(self, event):

        label = "HIGH" if self.isChecked() else "LOW"
        bg_color = Qt.red if self.isChecked() else Qt.green

        if not self.isEnabled():
            bg_color = Qt.gray
            label = "???"

        radius = 10
        width = 40
        center = self.rect().center()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.translate(center)
        painter.setBrush(QtGui.QColor(0,0,0))

        pen = QtGui.QPen(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawRoundedRect(QRect(-width, -radius, 2*width, 2*radius), radius, radius)
        painter.setBrush(QtGui.QBrush(bg_color))
        sw_rect = QRect(-radius, -radius, width + radius, 2*radius)
        if not self.isChecked():
            sw_rect.moveLeft(-width)
        painter.drawRoundedRect(sw_rect, radius, radius)
        painter.drawText(sw_rect, Qt.AlignCenter, label)
        painter.end()

inputs_global: tp.List[QLabel] = []
outputs_global: tp.List[PrettySwitch] = []
outputs_names_global: tp.List[QLineEdit] = []
ip_line_edit: QLineEdit = None
status_label: QLabel = None
main_window: QWidget = None

class ExchangeThread(QtCore.QThread):
    update = QtCore.pyqtSignal(str)
    delay = 0.5

    def __init__(self, parent=None):
        super(ExchangeThread, self).__init__(parent)
        self.is_running = True

    def run(self):
        while self.is_running:
            try:
                self.exchangeData()
                self.enableButtons(True)
                self.update.emit(f"Ok")
                for output in outputs_global:
                    output.changed = False
            except Exception as e:
                print(e)
                self.update.emit(str(e))
                self.enableButtons(False)
            time.sleep(ExchangeThread.delay)

    def stop(self):
        self.is_running = False

    def enableButtons(self, enabled: bool) -> None:
        for switch in outputs_global:
            switch.setEnabled(enabled)
        if not enabled:
            for input in inputs_global:
                input.setText("???")

    def updateState(self, arduino_state: str):

        print(f"GOT STATE: {arduino_state}")

        "6outputs 8inputs+"
        outputs = map(int, arduino_state[:OUTPUTS_COUNT])
        inputs = map(int, arduino_state[OUTPUTS_COUNT + 1:OUTPUTS_COUNT + INPUTS_COUNT + 1])

        for idx, output in enumerate(outputs):
            if not outputs_global[idx].changed:
                outputs_global[idx].setChecked(output)

        for idx, input in enumerate(inputs):
            inputs_global[idx].setText("HIGH" if input else "LOW")
            inputs_global[idx].setStyleSheet(f"background-color: {'#FF0000' if input else '#00FF00'}")

    def getState(self) -> str:
        state = "".join([str(int(sw.isChecked())) for sw in outputs_global])
        return state

    def exchangeData(self):

        if not checkIPAddress(ip_line_edit.text()):
            raise Exception("ERROR IP-address format")

        tcp_socket = QTcpSocket()
        tcp_socket.connectToHost(ip_line_edit.text(), 80, QIODevice.ReadWrite)
        self.update.emit(f"Connecting to {tcp_socket.peerAddress().toString()}:{tcp_socket.peerPort()}")

        if not tcp_socket.waitForConnected(5000):
            raise Exception(f"ERROR connecting to {ip_line_edit.text()}:80")

        tcp_socket.waitForReadyRead(5000)
        arduino_state: bytes = b""
        while tcp_socket.bytesAvailable() > 0:
            arduino_state += tcp_socket.readAll().data()
        print(arduino_state)

        arduino_state = arduino_state.decode()
        if ("+" not in arduino_state):
            raise Exception(f"ERROR incomplete read")

        self.updateState(arduino_state)

        tcp_socket.write((self.getState() + "+\n").encode("utf-8"))
        tcp_socket.flush()

        if tcp_socket.bytesToWrite() > 0:
            raise Exception(f"ERROR incomplete write")

        tcp_socket.disconnectFromHost()
        tcp_socket.close()

def checkIPAddress(ip_address):
    try:
        ip_parts = ip_address.split('.')
        return (len(ip_parts) == 4) and all((0 < len(part) < 4) and (0 <= int(part) < 256) for part in ip_parts)
    except ValueError:
        return False
    except (AttributeError, TypeError):
        return False

def killExchangeThread(thread: ExchangeThread):
    thread.stop()
    thread.wait()

def save_config() -> None:

    file_name = QFileDialog.getSaveFileName(main_window, "Save config")[0]

    if not file_name:
        return

    config = dict()
    config["ip_line_edit"] = ip_line_edit.text()

    config["outputs_names_global"] = []
    for name in outputs_names_global:
        config["outputs_names_global"].append(name.text())

    print(f"Saving config to {file_name}")
    with open(file_name, "w") as f:
        json.dump(config, f)

    main_window.setWindowTitle(f"Arduino PIN controller: {os.path.basename(file_name)}")

def load_config() -> None:

    file_name = QFileDialog.getOpenFileName(main_window, "Load config config")[0]

    if not file_name:
        return

    print(f"Loading config from {file_name}")
    with open(file_name) as f:
        config = json.load(f)

    ip_line_edit.setText(config["ip_line_edit"])

    for idx, name in enumerate(config["outputs_names_global"]):
        outputs_names_global[idx].setText(name)

    main_window.setWindowTitle(f"Arduino PIN controller: {os.path.basename(file_name)}")

def main():

    app = QApplication([])
    global main_window
    main_window = QWidget()

    buttons_layout = QGridLayout()
    for i in range(OUTPUTS_COUNT):
        buttons_layout.addWidget(QLabel(f"PIN {i+4}"), i, 0, Qt.AlignRight)

        edit = QLineEdit("")
        outputs_names_global.append(edit)
        buttons_layout.addWidget(edit, i, 1)

        switch = PrettySwitch()
        switch.setEnabled(False)
        switch.toggled.connect(lambda x, i=i: print(f"SET PIN {i+4} = {'HIGH' if x else 'LOW'}"))
        outputs_global.append(switch)
        buttons_layout.addWidget(switch, i, 2)

    inputs_layout = QGridLayout()
    for i in range(INPUTS_COUNT):
        inputs_layout.addWidget(QLabel(f"A{i}"), 0, i, Qt.AlignCenter)
        label = QLabel("???")
        inputs_global.append(label)
        inputs_layout.addWidget(label, 1, i, Qt.AlignCenter)

    main_layout = QGridLayout()
    main_layout.addLayout(buttons_layout, 0, 0, Qt.AlignCenter)
    main_layout.addLayout(inputs_layout, 1, 0)

    ip_layout = QGridLayout()
    ip_range = "(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])"
    ip_regex = QRegExp("^" + ip_range + "\\." + ip_range + "\\." + ip_range + "\\." + ip_range + "$")
    ip_validator = QRegExpValidator(ip_regex)
    global ip_line_edit
    ip_line_edit = QLineEdit(main_window)
    ip_line_edit.setPlaceholderText("192.168.0.1")
    ip_line_edit.setValidator(ip_validator)
    ip_line_edit.setFocusPolicy(Qt.StrongFocus)
    ip_line_edit.setFocus()
    ip_layout.addWidget(ip_line_edit, 0, 0)

    save_button = QPushButton("Save")
    save_button.clicked.connect(save_config)
    ip_layout.addWidget(save_button, 0, 1)

    load_button = QPushButton("Load")
    load_button.clicked.connect(load_config)
    ip_layout.addWidget(load_button, 0, 2)
    main_layout.addLayout(ip_layout, 2, 0)

    status_layout = QGridLayout()
    global status_label
    status_label = QLabel("?")
    status_layout.addWidget(QLabel("STATUS: "), 0, 0)
    status_layout.addWidget(status_label, 0, 1, Qt.AlignLeft)
    status_layout.addWidget(QLabel(""), 0, 2, Qt.AlignLeft)
    main_layout.addLayout(status_layout, 3, 0)

    exchange_thread = ExchangeThread()
    exchange_thread.update.connect(lambda status: status_label.setText(status[:35]))
    exchange_thread.start()

    #window.setGeometry(100, 100, 200, 300)
    main_window.setWindowTitle("Arduino PIN controller")
    main_window.setLayout(main_layout)
    main_window.setFixedSize(400, 400)
    main_window.show()

    app.lastWindowClosed.connect(lambda: killExchangeThread(exchange_thread))

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
