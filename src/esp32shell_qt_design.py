# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'esp32shell_qt_design.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from serialterminalwidget import SerialTerminalWidget


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(895, 739)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.commandlist = QListWidget(self.centralwidget)
        self.commandlist.setObjectName(u"commandlist")
        self.commandlist.setGeometry(QRect(30, 120, 231, 571))
        self.label_commandlist = QLabel(self.centralwidget)
        self.label_commandlist.setObjectName(u"label_commandlist")
        self.label_commandlist.setGeometry(QRect(30, 100, 161, 16))
        self.text_output = QTextEdit(self.centralwidget)
        self.text_output.setObjectName(u"text_output")
        self.text_output.setGeometry(QRect(290, 120, 581, 311))
        self.command_input = QLineEdit(self.centralwidget)
        self.command_input.setObjectName(u"command_input")
        self.command_input.setGeometry(QRect(30, 70, 841, 20))
        self.label_command_input = QLabel(self.centralwidget)
        self.label_command_input.setObjectName(u"label_command_input")
        self.label_command_input.setGeometry(QRect(30, 40, 111, 16))
        self.label_output = QLabel(self.centralwidget)
        self.label_output.setObjectName(u"label_output")
        self.label_output.setGeometry(QRect(290, 100, 47, 13))
        self.Repl = SerialTerminalWidget(self.centralwidget)
        self.Repl.setObjectName(u"Repl")
        self.Repl.setGeometry(QRect(290, 460, 581, 231))
        self.label_repl = QLabel(self.centralwidget)
        self.label_repl.setObjectName(u"label_repl")
        self.label_repl.setGeometry(QRect(300, 440, 90, 16))
        self.radioButton_commandmode = QRadioButton(self.centralwidget)
        self.radioButton_commandmode.setObjectName(u"radioButton_commandmode")
        self.radioButton_commandmode.setGeometry(QRect(130, 40, 141, 20))
        self.radioButton_commandmode.setChecked(True)
        self.radioButton_replmode = QRadioButton(self.centralwidget)
        self.radioButton_replmode.setObjectName(u"radioButton_replmode")
        self.radioButton_replmode.setGeometry(QRect(270, 40, 121, 20))
        self.label_comport = QLabel(self.centralwidget)
        self.label_comport.setObjectName(u"label_comport")
        self.label_comport.setGeometry(QRect(30, 10, 441, 16))
        self.label_srcpath = QLabel(self.centralwidget)
        self.label_srcpath.setObjectName(u"label_srcpath")
        self.label_srcpath.setGeometry(QRect(380, 40, 81, 20))
        self.lineEdit_srcpath = QLineEdit(self.centralwidget)
        self.lineEdit_srcpath.setObjectName(u"lineEdit_srcpath")
        self.lineEdit_srcpath.setGeometry(QRect(480, 40, 391, 20))
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 895, 21))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label_commandlist.setText(QCoreApplication.translate("MainWindow", u"Command list", None))
        self.label_command_input.setText(QCoreApplication.translate("MainWindow", u"Command", None))
        self.label_output.setText(QCoreApplication.translate("MainWindow", u"Output", None))
        self.label_repl.setText(QCoreApplication.translate("MainWindow", u"Repl", None))
        self.radioButton_commandmode.setText(QCoreApplication.translate("MainWindow", u"Command mode", None))
        self.radioButton_replmode.setText(QCoreApplication.translate("MainWindow", u"REPL mode", None))
        self.label_comport.setText(QCoreApplication.translate("MainWindow", u"COM: ", None))
        self.label_srcpath.setText(QCoreApplication.translate("MainWindow", u"Source path", None))
    # retranslateUi

