from qgis.core import QgsCoordinateReferenceSystem, QgsWkbTypes, Qgis
from qgis.PyQt.QtWidgets import QDialogButtonBox, QWidget, QDialog, QProgressBar, QComboBox
from qgis.utils import iface

from risteyslaskenta_package.risteyslaskenta_functions import (
    convert_polygons_to_centroids,
    create_result_layer,
    process_intersection,
)


from ..qgis_plugin_tools.tools.resources import load_ui  # type: ignore

FORM_CLASS: QWidget = load_ui("risteyslaskenta_dialog.ui")


class RisteyslaskentaDialog(QDialog, FORM_CLASS):  # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.setupUi(self)
        self.iface = iface
        self.traffic_combobox: QComboBox
        self.intersection_combobox: QComboBox
        self.button_box: QDialogButtonBox
        self.progress_bar: QProgressBar

        self.button_box.button(QDialogButtonBox.Ok).setText("Run")
        self.button_box.accepted.connect(self._on_run_clicked)


    def _on_run_clicked(self):
        # Reset progress bar
        self.progress_bar.setValue(0)

        # Selections
        data_layer = self.traffic_combobox.currentLayer()
        points_layer = self.intersection_combobox.currentLayer()

        # Convert input data if needed
        if points_layer.geometryType() == QgsWkbTypes.PolygonGeometry:
            points_layer = convert_polygons_to_centroids(points_layer)

        # Crs from data layer
        crs = QgsCoordinateReferenceSystem()
        crs.createFromProj(points_layer.crs().toProj())
        result_layer = create_result_layer(crs, data_layer.fields())

        # Iterate each intersection
        # We want to handle one intersection at a time to create visuals that
        # would overlap as little as possible
        # We count the number of all intersections and "failed" intersections
        # for additional info and print it
        index = data_layer.fields().indexOf("id")
        intersections = data_layer.uniqueValues(index)
        failed_sum = 0
        intersection_count = len(intersections)
        for i, intersection in enumerate(intersections):
            if not process_intersection(
                points_layer, data_layer, result_layer, intersection
            ):
                failed_sum += 1
            progress = int(i / intersection_count * 100)
            self.progress_bar.setValue(progress)
        print("Total number of intersections: {}".format(intersection_count))
        print(
            "Number of intersections without any location features: {}".format(
                failed_sum
            )
        )
        self.progress_bar.setValue(100)

        result_layer.commitChanges()
        iface.vectorLayerTools().stopEditing(result_layer)

        if failed_sum == intersection_count:
            iface.messageBar().pushMessage(
                "Warning", f"Risteyslaskenta processing failed (no location features found for any intersection). ",
                level=Qgis.Warning
            )
        else:
            iface.messageBar().pushMessage(
                "Success",
                f"Risteyslaskenta processing completed succesfully. Features found for {intersection_count-failed_sum}/{intersection_count} given intersections",
                level=Qgis.Success
            )

        self.accept()
