from PySide6 import QtWidgets, QtCore
from functools import partial

import pyqtgraph as pg

import time, socket
import matplotlib as plt

class PortListWidgetItem(QtWidgets.QListWidgetItem):
    def __lt__(self, other):
        try:
            return float(self.text().split('-')[1]) < float(other.text().split('-')[1])
        except Exception:
            return QListWidgetItem.__lt__(self, other)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, scommand, swaveform):
        super().__init__()

        self.scommand = scommand
        self.swaveform = swaveform

        self.setWindowTitle("EMG Game Controller")

        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.vbox0 = QtWidgets.QVBoxLayout(self.central_widget)

        self.hbox0 = QtWidgets.QHBoxLayout()

        self.port_selection_grp = QtWidgets.QGroupBox()
        self.port_selection_grp.setTitle("Port Selection")
        self.hbox0.addWidget(self.port_selection_grp)

        self.port_selection_grp_vbox0 = QtWidgets.QVBoxLayout()
        self.port_selection_grp.setLayout(self.port_selection_grp_vbox0)
        self.port_selection_grp.setMaximumWidth(200)

        self.port_selection_grp_vbox0.addWidget(QtWidgets.QLabel("Available Ports:"))
        self.available_ports = QtWidgets.QListWidget()
        for x in range(32):
            self.available_ports.addItem(PortListWidgetItem(f"A-{x:03}"))
        self.available_ports.itemDoubleClicked.connect(self.add_to_selected_ports)
        self.available_ports.setSortingEnabled(True)
        self.port_selection_grp_vbox0.addWidget(self.available_ports)

        self.port_selection_grp_vbox0.addWidget(QtWidgets.QLabel("Selected Ports:"))
        self.selected_ports = QtWidgets.QListWidget()
        self.selected_ports.itemDoubleClicked.connect(self.remove_from_selected_ports)
        self.selected_ports.setSortingEnabled(True)
        self.port_selection_grp_vbox0.addWidget(self.selected_ports)

        self.plot_zone = pg.PlotWidget()
        self.plot_zone.setMinimumWidth(500)
        self.hbox0.addWidget(self.plot_zone)

        self.button_grp = QtWidgets.QGroupBox()
        self.button_grp.setTitle("asdfasdfsa")
        self.button_grp.setMaximumWidth(200)
        self.button_grp.setEnabled(True)
        self.hbox0.addWidget(self.button_grp)

        self.button_grp_vbox0 = QtWidgets.QVBoxLayout()
        self.button_grp.setLayout(self.button_grp_vbox0)

        self.plotButton = QtWidgets.QPushButton("Do Plot")
        self.plotButton.clicked.connect(self.draw_plot)
        self.button_grp_vbox0.addWidget(self.plotButton)

        self.calibrationButton = QtWidgets.QPushButton("Calibration")
        self.calibrationButton.clicked.connect(partial(self.begin_calibration, "Relax", 6))
        self.button_grp_vbox0.addWidget(self.calibrationButton)

        self.gameButton = QtWidgets.QPushButton("Begin Game")
        self.gameButton.clicked.connect(lambda: self.write_to_cmd("a"))
        self.button_grp_vbox0.addWidget(self.gameButton)

        self.info = QtWidgets.QLabel("asdf: 1")
        self.button_grp_vbox0.addWidget(self.info)

        self.vbox0.addLayout(self.hbox0)

        self.cmd_display = QtWidgets.QTextEdit("asdf")
        self.cmd_display.setReadOnly(True)

        self.vbox0.addWidget(self.cmd_display)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)

    def write_to_cmd(self, msg: str):
        previous_text = '\n'.join(self.cmd_display.toPlainText().split('\n')[-50:])
        self.cmd_display.setText(f"{previous_text}\n{msg}")
        self.cmd_display.verticalScrollBar().setValue(
            self.cmd_display.verticalScrollBar().maximum()
        )

    def add_to_selected_ports(self, double_clicked_port):
        if self.selected_ports.count() == 2:
            self.write_to_cmd("You may only select up to two ports.")
            return
        self.selected_ports.addItem(PortListWidgetItem(double_clicked_port.text()))
        self.available_ports.takeItem(self.available_ports.row(double_clicked_port))
        self.scommand.sendall(f"set {double_clicked_port.text().lower()}.tcpdataoutputenabled true".encode())
        self.write_to_cmd(f"Analog port: {double_clicked_port.text()} has been activated.")
        self.available_ports.sortItems()
        self.selected_ports.sortItems()
        time.sleep(0.1)


    def remove_from_selected_ports(self, double_clicked_port):
        self.available_ports.addItem(PortListWidgetItem(double_clicked_port.text()))
        self.selected_ports.takeItem(self.selected_ports.row(double_clicked_port))
        self.scommand.sendall(f"set {double_clicked_port.text().lower()}.tcpdataoutputenabled false".encode())
        self.write_to_cmd(f"Analog port: {double_clicked_port.text()} has been deactivated.")
        self.available_ports.sortItems()
        self.selected_ports.sortItems()
    
    def draw_plot(self):
        asdf = {
            "time": [0.01, 0.1, 1, 10, 100, 1000, 10000],
            "value": [5, 10, 20, 30, 20, 10, 0],
        }

        # plot data: x, y values
        self.plot_zone.setTitle("Power Spectral Density")
        self.plot_zone.setLabel(axis="left", text="Magnitude")
        self.plot_zone.setLabel(axis="bottom", text="Freq")
        self.plot_zone.getAxis("bottom").setLogMode(True)
        self.plot_zone.plot(
            asdf["time"], asdf["value"])

    def begin_calibration(self, stage, sec_remaining):
        if sec_remaining == 6:
            self.write_to_cmd(f"Begin calibration for {stage}...")
        elif sec_remaining == 0:
            self.end_calibration(stage)
            if stage == "Relax":
                QtCore.QTimer.singleShot(2000, partial(self.begin_calibration, "Flex", 6))
            elif stage == "Flex":
                QtCore.QTimer.singleShot(2000, partial(self.begin_calibration, "Double Flex", 6))
            return
        else:
            self.write_to_cmd(f"... {sec_remaining}")
        QtCore.QTimer.singleShot(1000, partial(self.begin_calibration, stage, sec_remaining - 1))

    def end_calibration(self, stage):
        self.write_to_cmd(f"End calibration for {stage}")


    def tick(self):
        pass

def readUint32(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 4]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=False)
    arrayIndex = arrayIndex + 4
    return variable, arrayIndex

def readInt32(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 4]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=True)
    arrayIndex = arrayIndex + 4
    return variable, arrayIndex

def readUint16(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 2]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=False)
    arrayIndex = arrayIndex + 2
    return variable, arrayIndex

COMMAND_BUFFER_SIZE = 1024

WAVEFORM_BUFFER_SIZE = 400000

def main():
    print('Connecting to TCP command server...')
    scommand = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            scommand.connect(('127.0.0.1', 5000))
        except ConnectionRefusedError:
            print("Connection to TCP command server unsucessful.\n Trying again...")
        else:
            break

    print('Connecting to TCP waveform server...')
    swaveform = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            swaveform.connect(('127.0.0.1', 5001))
        except ConnectionRefusedError:
            print("Connection to TCP waveform server unsuccessful.\n Trying again...")
        else:
            break
    
    scommand.sendall(b'get runmode')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    isStopped = commandReturn == "Return: RunMode Stop"

    if not isStopped:
        scommand.sendall(b'set runmode stop')
        time.sleep(0.1)

    scommand.sendall(b'get sampleratehertz')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    expectedReturnString = "Return: SampleRateHertz "
    if commandReturn.find(expectedReturnString) == -1: # Look for "Return: SampleRateHertz N" where N is the sample rate
        raise Exception('Unable to get sample rate from server')
    else:
        sampleRate = float(commandReturn[len(expectedReturnString):])

    timestep = 1 / sampleRate

    #scommand.sendall(b'execute clearalldataoutputs')
    scommand.sendall(b'set runmode run')
    time.sleep(1)
    scommand.sendall(b'set runmode stop')
    rawData = swaveform.recv(WAVEFORM_BUFFER_SIZE)
    print(len(rawData))

    app = QtWidgets.QApplication([])
    window = MainWindow(scommand,swaveform)
    window.show()
    app.exec()

if __name__ == '__main__':
    main()