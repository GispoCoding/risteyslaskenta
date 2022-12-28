from math import sqrt
from typing import Tuple

import numpy as np
from qgis.core import (
    QgsCircularString,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPalLayerSettings,
    QgsPoint,
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
    result_layer = QgsVectorLayer("CompoundCurve", "temp", "memory")
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


def perpendicular(coords: Tuple[float, float]):
    perpendicular_vector = np.empty_like(coords)
    perpendicular_vector[0] = -coords[1]
    perpendicular_vector[1] = coords[0]
    return perpendicular_vector


def normalize(array):
    array = np.array(array)
    return array / np.linalg.norm(array)


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    x = (p1[0] - p2[0]) ** 2
    y = (p1[1] - p2[1]) ** 2
    distance = sqrt(x + y)
    return distance


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
    start_point: QgsPointXY,
    end_point: QgsPointXY,
    intersection_middle_point,
    straight_road=False,
) -> QgsPointXY:
    mid_x = (start_point.x() + end_point.x()) / 2
    mid_y = (start_point.y() + end_point.y()) / 2

    # If distance to centre is more than 2m, likely a turn
    if not straight_road:
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

    nr_of_branches = max([int(feat["Haara"]) for feat in location_feats])
    moved_list = []

    for data_feat in data_feats:
        start_point, end_point = None, None
        x_coords = set([feat.geometry().asPoint().x() for feat in location_feats])
        y_coords = set([feat.geometry().asPoint().y() for feat in location_feats])
        intersection_center_point = sum(x_coords) / len(x_coords), sum(y_coords) / len(
            y_coords
        )

        for location_feat in location_feats:

            if str(location_feat["Haara"]) == data_feat["direction"][0]:
                start_point = location_feat.geometry().asPoint()
            elif str(location_feat["Haara"]) == data_feat["direction"][1]:
                end_point = location_feat.geometry().asPoint()
            if start_point and end_point:
                break

        if (
            nr_of_branches == 4
            and abs(int(data_feat["direction"][0]) - int(data_feat["direction"][1]))
            == 2
        ):
            straight_road = True
        else:
            straight_road = False

        if start_point and end_point:
            # Calculate middle point for curve
            middle_point = calculate_middle_point(
                start_point, end_point, intersection_center_point, straight_road
            )
            # If the intersection branches are oddly placed, we need to make correction
            # If this was not done, some intersections would have large round curves
            if distance(
                (middle_point.x(), middle_point.y()), (end_point.x(), end_point.y())
            ) > distance(
                (start_point.x(), start_point.y()), (end_point.x(), end_point.y())
            ):
                mid_x = (start_point.x() + end_point.x()) / 2
                mid_y = (start_point.y() + end_point.y()) / 2
                middle_point = QgsPointXY(mid_x, mid_y)

            # Calculate perpendicular and normalized vector of a straight line
            # from intersection branch to another
            unit_vector = normalize(
                perpendicular(
                    (end_point.x() - start_point.x(), end_point.y() - start_point.y())
                )
            )

            if straight_road:
                move_vector = 2 * unit_vector
            else:
                # Move the start and end points away from intersection center
                # First make sure the direction is away from the intersection center
                if distance(
                    (start_point.x(), start_point.y()), intersection_center_point
                ) > distance(
                    (
                        start_point.x() + unit_vector[0],
                        start_point.y() + unit_vector[1],
                    ),
                    intersection_center_point,
                ):
                    unit_vector = -unit_vector
                # If the curve being drawn is 2nd for a branch pair, move it further
                if data_feat["direction"][::-1] in moved_list:
                    move_vector = 10 * unit_vector
                else:
                    move_vector = 6 * unit_vector
                    moved_list.append(data_feat["direction"])
            start_point = QgsPointXY(
                start_point.x() + move_vector[0], start_point.y() + move_vector[1]
            )
            middle_point = QgsPointXY(
                middle_point.x() + move_vector[0], middle_point.y() + move_vector[1]
            )
            end_point = QgsPointXY(
                end_point.x() + move_vector[0], end_point.y() + move_vector[1]
            )

            feat = QgsFeature(result_layer.fields())
            circular_ring = QgsCircularString(
                QgsPoint(start_point), QgsPoint(middle_point), QgsPoint(end_point)
            )
            geom = QgsGeometry(circular_ring)
            feat.setGeometry(geom)

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
