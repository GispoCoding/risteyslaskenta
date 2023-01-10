from math import sqrt
from typing import List, Tuple

import numpy as np
from qgis import processing
from qgis.core import (
    QgsCircularString,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant


def create_result_layer(crs) -> QgsVectorLayer:
    """Create the result layer and add it to QGIS layers.

    The result layer geometry type is Line (CompoundCurve) in QGIS and the
    individual features added will be QgsCircularStrings. The attributes/data columns
    are defined here. No data is added at this stage."""
    result_layer = QgsVectorLayer("CompoundCurve", "temp", "memory")
    result_layer.setCrs(crs)
    result_layer.dataProvider().addAttributes(
        [
            QgsField("id", QVariant.String),
            QgsField("intersection", QVariant.String),
            QgsField("direction", QVariant.String),
            QgsField("start_direction", QVariant.String),
            QgsField("cars", QVariant.Double),
            QgsField("max_cars_in_intersection", QVariant.Double),
            QgsField("min_cars_in_intersection", QVariant.Double),
            QgsField("cars_intersection_normalized", QVariant.Double),
            QgsField("feat_length", QVariant.Double),
        ]
    )
    result_layer.updateFields()
    result_layer.setName("Intersections visualized")
    QgsProject.instance().addMapLayer(result_layer)
    return result_layer


def perpendicular(vector: Tuple[float, float]) -> np.ndarray:
    """Calculates a vector perpendicular to the given input vector.

    This function is used to calculate the move vector for a curve
    geometry."""
    perpendicular_vector = np.empty_like(vector)
    perpendicular_vector[0] = -vector[1]
    perpendicular_vector[1] = vector[0]
    return perpendicular_vector


def normalize(array) -> np.ndarray:
    """Normalize an input array and convert to Numpy array."""
    array = np.array(array)
    return array / np.linalg.norm(array)


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculates distance between points in 2D space. Pythagorean theorem."""
    x = (p1[0] - p2[0]) ** 2
    y = (p1[1] - p2[1]) ** 2
    distance = sqrt(x + y)
    return distance


def convert_polygons_to_centroids(polygon_layer: QgsVectorLayer) -> QgsVectorLayer:
    """Calls QGIS own algorithm to convert a polygon layer to centroid point layer.

    This is used if intersection branches are represented as polygons initially."""
    parameters = {"INPUT": polygon_layer, "OUTPUT": "memory:"}
    result = processing.run("native:centroids", parameters)
    layer = result["OUTPUT"]
    print("Converted a polygon layer to a point layer")
    return layer


def calculate_middle_point(
    start_point: QgsPointXY,
    end_point: QgsPointXY,
    intersection_middle_point,
    straight_road=False,
) -> QgsPointXY:
    """Calculates the middle point between start and end points.

    If the road geometry for which this is calculated is determined not
    to be straight, the middle point is moved towards the intersection center,
    to create a curve that represents a turn in an intersection.

    Sometimes the interesction center is not in a logical place due to unusual
    geometry or errors in data. In these cases, we revert creating the curve
    and make a straight line."""
    mid_x = (start_point.x() + end_point.x()) / 2
    mid_y = (start_point.y() + end_point.y()) / 2

    # If the road is determined to be not straight, adjust middle point
    # to create a curve
    if not straight_road:
        mid_x = (mid_x + intersection_middle_point[0]) / 2
        mid_y = (mid_y + intersection_middle_point[1]) / 2
    middle_point = QgsPointXY(mid_x, mid_y)

    # If the intersection branches/center are oddly placed, we need to make correction
    # If this wouldnt be done, some intersections would have large, very circular curves

    if distance(
        (middle_point.x(), middle_point.y()), (end_point.x(), end_point.y())
    ) > distance((start_point.x(), start_point.y()), (end_point.x(), end_point.y())):
        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        middle_point = QgsPointXY(mid_x, mid_y)

    return middle_point


def calculate_intersection_center_point(
    location_feats: List[QgsFeature],
) -> tuple[float, float]:
    """Calculates the intersection center point based on location of intersection branches.

    Intersection center point is used in creating the curve geometries by shifting the
    curve middle point towards intersection center. Duplicate branch locations are not
    counted, so only unique points count."""
    x_coords = set([feat.geometry().asPoint().x() for feat in location_feats])
    y_coords = set([feat.geometry().asPoint().y() for feat in location_feats])
    intersection_center_point = sum(x_coords) / len(x_coords), sum(y_coords) / len(
        y_coords
    )
    return intersection_center_point


def find_start_and_end_points(
    data_feat: QgsFeature, location_feats: List[QgsFeature]
) -> tuple[QgsPointXY, QgsPointXY]:
    """Tries to find matching branch location features for an intersection data feature.

    The location point features are used as start and end point features to draw the
    visualization curve on map. If no matches are found, None-types are returned and
    this data feature cannot be visualized."""
    start_point, end_point = None, None
    for location_feat in location_feats:
        if str(location_feat["Haara"]) == data_feat["direction"][0]:
            start_point = location_feat.geometry().asPoint()
        elif str(location_feat["Haara"]) == data_feat["direction"][1]:
            end_point = location_feat.geometry().asPoint()
        if start_point and end_point:
            break
    return start_point, end_point


def determine_straight_road(
    data_feat: QgsFeature, location_feats: List[QgsFeature]
) -> bool:
    """Determine if an intersection branch pair is likely a straight road.

    Currently, a road is deemed straight if 2 things apply: The whole intersection
    has exactly 4 branches, and this branch pair / road has ID's with a difference of 2
    (e.g. 1 and 3, or 2 and 4)"""
    nr_of_branches = max([int(feat["Haara"]) for feat in location_feats])
    if (
        nr_of_branches == 4
        and abs(int(data_feat["direction"][0]) - int(data_feat["direction"][1])) == 2
    ):
        return True
    else:
        return False


def calculate_move_vector(
    data_feat: QgsFeature,
    start_point: QgsPointXY,
    intersection_center_point: tuple[float, float],
    unit_vector: np.ndarray,
    moved_list: List[str],
) -> tuple[np.ndarray, List[str]]:
    """Calculate the vector by which a visualized line is moved.

    Moving of the visuals is done to minimize overlapping. For different
    directions but same branch pair, moved_list is used and move vector
    is higher for the second curve of the pair. If there is data from multiple
    days and/or times, this overlapping cannot be avoided as of now."""

    # Move the start and end points away from intersection center
    # First make sure the direction is away from the intersection center
    if distance(
        (start_point.x(), start_point.y()), intersection_center_point
    ) > distance(
        (start_point.x() + unit_vector[0], start_point.y() + unit_vector[1]),
        intersection_center_point,
    ):
        unit_vector = -unit_vector
    # If the curve being drawn is 2nd for a branch pair (so the same pair but reverse
    # direction is found in moved_list), move it further to avoid overlap
    if data_feat["direction"][::-1] in moved_list:
        move_vector = 10 * unit_vector
    else:
        move_vector = 6 * unit_vector
        moved_list.append(data_feat["direction"])
    return move_vector, moved_list


def create_and_add_feature(
    data_feat: QgsFeature,
    result_layer: QgsVectorLayer,
    start_point: QgsPointXY,
    mid_point: QgsPointXY,
    end_point: QgsPointXY,
    move_vector: np.ndarray,
) -> QgsFeature:
    """Create the curve feature (CircularString) that represents traffic from one
    intersection branch to another and add it to the result layer.

    The calculated move vector is utilized here to shift the points before creating
    the curve geometry. Attribute data is set here as much as possible."""
    start_point = QgsPointXY(
        start_point.x() + move_vector[0], start_point.y() + move_vector[1]
    )
    middle_point = QgsPointXY(
        mid_point.x() + move_vector[0], mid_point.y() + move_vector[1]
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
            data_feat["direction"][0],
            data_feat["autot"],
            -9999,
            -9999,
            -9999,
            circular_ring.length(),
        ]
    )
    _ = result_layer.dataProvider().addFeature(feat)
    return feat


def process_intersection(
    points_layer: QgsVectorLayer,
    data_layer: QgsVectorLayer,
    result_layer: QgsVectorLayer,
    intersection_id,
) -> bool:
    """The main function that runs through processing and visualizing a whole intersection.

    The steps:
    1. Select features
    2. Check if we found any location features
    3. Find intersection center point
    4. Initialize some values before loop
    5. Loop data feats
        1. Find the correct branch location feats for the data feat
        2. Check if the branch location pair seems like a straight road
        3. Calculate middle point for to-be-drawn visual
        4. Calculate a vector perpendicular to the branch location pair
        5. Calculate a move vector and move the points accordingly
        6. Create a curved line feature from the points (the actual visualization)
    6. Update some intersection attributes
    """

    print("Intersection id is type string: {}".format(isinstance(intersection_id, str)))
    print("Intersection id is type int: {}".format(isinstance(intersection_id, int)))
    # 1
    data_layer.selectByExpression("id = '{}'".format(intersection_id))
    data_feats = data_layer.selectedFeatures()

    points_layer.selectByExpression("RPH = '{}'".format(intersection_id))
    location_feats = points_layer.selectedFeatures()

    # 2
    if len(location_feats) == 0:
        return False

    # 3
    intersection_center_point = calculate_intersection_center_point(location_feats)

    # 4
    moved_list: List[str] = []
    added_features: List[QgsFeature] = []
    intersection_max_value = 0
    intersection_min_value = None

    # 5
    for data_feat in data_feats:

        # 5.1
        start_point, end_point = find_start_and_end_points(data_feat, location_feats)

        # 5.2
        straight_road = determine_straight_road(data_feat, location_feats)

        if start_point and end_point:
            # Update intersection max and min value
            if int(data_feat["autot"]) > intersection_max_value:
                intersection_max_value = int(data_feat["autot"])
            if (
                intersection_min_value is None
                or int(data_feat["autot"]) < intersection_min_value
            ):
                intersection_min_value = int(data_feat["autot"])

            # 5.3
            middle_point = calculate_middle_point(
                start_point, end_point, intersection_center_point, straight_road
            )

            # Calculate perpendicular and normalized vector of a straight line
            # from intersection branch to another
            # 5.4
            unit_vector = normalize(
                perpendicular(
                    (end_point.x() - start_point.x(), end_point.y() - start_point.y())
                )
            )

            # 5.5
            if straight_road:
                move_vector = 2 * unit_vector
            else:
                move_vector, moved_list = calculate_move_vector(
                    data_feat,
                    start_point,
                    intersection_center_point,
                    unit_vector,
                    moved_list,
                )

            # 5.6
            feat = create_and_add_feature(
                data_feat,
                result_layer,
                start_point,
                middle_point,
                end_point,
                move_vector,
            )
            added_features.append(feat)

    # 6
    for feat in added_features:
        intersection_min_value = 0
        normalized_value = (feat["cars"] - intersection_min_value) / (
            intersection_max_value - intersection_min_value
        )
        attrs = {
            5: intersection_max_value,
            6: intersection_min_value,
            7: normalized_value,
        }
        result_layer.dataProvider().changeAttributeValues({feat.id(): attrs})

    return True


def write_output_to_file(layer: QgsVectorLayer, output_path: str) -> None:
    """Writes the selected layer to a specified file"""
    writer_options = QgsVectorFileWriter.SaveVectorOptions()
    writer_options.actionOnExistingFile = QgsVectorFileWriter.AppendToLayerAddFields
    # PyQGIS documentation doesnt tell what the last 2 str error outputs
    # should be used for
    error, explanation = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer,
        output_path,
        QgsProject.instance().transformContext(),
        writer_options,
    )

    if error:
        print(
            f"Error writing output to file, error code {error}, details: {explanation}"
        )
