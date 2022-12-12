from qgis.PyQt import QtWidgets
from qgis.utils import iface

from ..qgis_plugin_tools.tools.resources import load_ui  # type: ignore

FORM_CLASS: QtWidgets.QWidget = load_ui("risteyslaskenta_dialog.ui")


class RisteyslaskentaDialog(QtWidgets.QDialog, FORM_CLASS):  # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.setupUi(self)
        self.iface = iface
