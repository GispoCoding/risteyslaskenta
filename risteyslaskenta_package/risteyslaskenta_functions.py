from functools import reduce

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont


def create_result_layer(crs) -> QgsVectorLayer:
    result_layer = QgsVectorLayer("LineString", "temp", "memory")
    result_layer.setCrs(crs)
    result_layer.dataProvider().addAttributes(
        [
            QgsField("id", QVariant.String),
            QgsField("intersection", QVariant.String),
            QgsField("direction", QVariant.String),
            QgsField("autot", QVariant.Double),
        ]
    )
    result_layer.updateFields()
    result_layer.setName("Intersections visualized")
    QgsProject.instance().addMapLayer(result_layer)
    return result_layer


# def convert_polygons_to_centroids(polygon_layer: QgsVectorLayer) -> QgsVectorLayer:
#     # points_layer = convert_polygon_to_point(points_layer)
#     iface.messageBar().pushMessage("Polygon layer detected, converting to points")
#     processing.runalg("qgis:polygoncentroids", polygon_layer, points_layer)
#     pass


def set_and_format_labels(layer: QgsVectorLayer) -> None:
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()
    text_format.setFont(QFont("FreeMono", 10))
    text_format.setSize(10)
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(0.1)
    buffer_settings.setColor(QColor("black"))
    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)
    layer_settings.fieldName = "id"
    layer_settings.placement = 0
    layer_settings.dist = 2.0
    layer_settings.enabled = True
    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)
    layer.triggerRepaint()


def check_same_crs(layer1, layer2) -> bool:
    if layer1.crs() == layer2.crs():
        return True
    else:
        return False


def calculate_middle_point(
    start_point: QgsPointXY, end_point: QgsPointXY, intersection_middle_point
) -> QgsPointXY:
    mid_x = (start_point.x() + end_point.x()) / 2
    mid_y = (start_point.y() + end_point.y()) / 2
    # If distance to centre is more than 2m, likely a turn
    if abs(mid_x - intersection_middle_point[0]) > 2:
        mid_x = (mid_x + intersection_middle_point[0]) / 2
        mid_y = (mid_y + intersection_middle_point[1]) / 2
    return QgsPointXY(mid_x, mid_y)


# This is now big O(n*m)
def create_lines_for_intersection(
    points_layer: QgsVectorLayer,
    data_layer: QgsVectorLayer,
    result_layer: QgsVectorLayer,
    intersection_id,
) -> bool:
    data_layer.selectByExpression("id = '{}'".format(intersection_id))
    data_feats = data_layer.selectedFeatures()

    points_layer.selectByExpression("RPH = '{}'".format(intersection_id))
    location_feats = points_layer.selectedFeatures()

    if len(location_feats) == 0:
        return False

    for data_feat in data_feats:
        start_point, end_point = None, None

        intersection_branches = []
        for location_feat in location_feats:
            intersection_branches.append(
                (
                    location_feat.geometry().asPoint().x(),
                    location_feat.geometry().asPoint().y(),
                )
            )

            if str(location_feat["Haara"]) == data_feat["direction"][0]:
                start_point = location_feat.geometry().asPoint()
            elif str(location_feat["Haara"]) == data_feat["direction"][1]:
                end_point = location_feat.geometry().asPoint()

        if start_point and end_point:
            intersection_center_point = reduce(
                lambda point1, point2: (
                    (point1[0] + point2[0]) / 2,
                    (point1[1] + point2[1]) / 2,
                ),
                intersection_branches,
            )
            line_middle_point = calculate_middle_point(
                start_point, end_point, intersection_center_point
            )

            feat = QgsFeature(result_layer.fields())
            feat.setGeometry(
                QgsGeometry.fromPolylineXY([start_point, line_middle_point, end_point])
            )
            feat.setAttributes(
                [
                    data_feat["fid"],
                    data_feat["id"],
                    data_feat["direction"],
                    data_feat["autot_num"],
                ]
            )
            _ = result_layer.dataProvider().addFeature(feat)

    return True


# def visualize_layer(layer):
#     line_symbol = QgsLineSymbol()
#     pass


def write_output_to_file(layer: QgsVectorLayer, output_path: str) -> None:
    """Writes the selected layer to a specified file"""
    writer_options = QgsVectorFileWriter.SaveVectorOptions()
    writer_options.actionOnExistingFile = QgsVectorFileWriter.AppendToLayerAddFields
    # PyQGIS documentation doesnt tell what the last 2 str error outputs
    # should be used for
    error, explanation, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        output_path,
        QgsProject.instance().transformContext(),
        writer_options,
    )

    if error:
        print(
            f"Error writing output to file, error code {error}, details: {explanation}"
        )
