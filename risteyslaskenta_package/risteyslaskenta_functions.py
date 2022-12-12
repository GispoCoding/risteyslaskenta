from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFillSymbol,
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
    # symbol = QgsFillSymbol.createSimple(
    #         {
    #             'color': 'transparent',
    #             'outline_color': 'blue',
    #             'outline_width': 0.5,
    #             'outline_style': 'dot'
    #         }
    #     )
    # result_layer.renderer().setSymbol(symbol)
    # result_layer.triggerRepaint()
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


def create_buffer(crs: str, point: QgsPointXY) -> QgsVectorLayer:
    buffer_layer = QgsVectorLayer("Polygon", "pointbuffer", "memory")
    buffer_layer.setCrs(crs)
    geom = QgsGeometry.fromPointXY(point)
    buffer_feat = QgsFeature()
    buffer_geom = geom.buffer(1, 10)
    buffer_feat.setGeometry(buffer_geom)
    buffer_layer.startEditing()
    buffer_layer.dataProvider().addFeature(buffer_feat)

    buffer_layer.setName("Intersecting circle")
    symbol = QgsFillSymbol.createSimple(
        {
            "color": "transparent",
            "outline_color": "blue",
            "outline_width": 0.5,
            "outline_style": "dot",
        }
    )
    buffer_layer.renderer().setSymbol(symbol)
    buffer_layer.triggerRepaint()
    buffer_layer.commitChanges()
    QgsProject.instance().addMapLayer(buffer_layer)
    return buffer_layer


# def convert_polygon_to_point(polygon_layer, crs_id):
#     point_layer = QgsVectorLayer("Line", "temp", "memory")

#     crs = QgsCoordinateReferenceSystem()
#     crs.createFromId(crs_id)
#     point_layer.setCrs(crs)

#     fields = polygon_layer.dataProvider().fields()
#     point_layer.dataProvider().addAttributes(fields)

#     point_layer.updateFields()
#     point_layer.setName("Intersections visualized")
#     point_layer.renderer().symbol().setColor(QColor.fromRgb(250, 0, 0))

#     x = []
#     y = []
#     for feat in polygon_layer.getFeatures():
#         for part in feat.geometry().parts():
#             x.append(part.x)
#             y.append(part.y)

#     pass


# def calculate_line_geometry(self, points_layer, intersection, direction):
#     intersection_feats = points_layer.selectByExpression(f"\"RPH\"={intersection}")

#     for feat in intersection_feats:
#         if str(feat['Haara']) == direction[0]:
#             start_point = feat.geometry().asPoint()
#         elif str(feat['Haara']) == direction[1]:
#             end_point = feat.geometry().asPoint()

#     points = [QgsPointXY(1,1), QgsPointXY(1,1), QgsPointXY(1,1)]
def check_same_crs(layer1, layer2) -> bool:
    if layer1.crs() == layer2.crs():
        return True
    else:
        return False


def calculate_middle_point(
    start_point: QgsPointXY, end_point: QgsPointXY, data_point: QgsPointXY
) -> QgsPointXY:
    mid_x = (start_point.x() + end_point.x()) / 2
    mid_y = (start_point.y() + end_point.y()) / 2
    data_x = data_point.x()
    data_y = data_point.y()
    # If distance to centre is more than 2m, likely a turn
    if abs(mid_x - data_x) > 2:
        mid_x = (mid_x + data_x) / 2
        mid_y = (mid_y + data_y) / 2
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

        for location_feat in location_feats:
            if str(location_feat["Haara"]) == data_feat["direction"][0]:
                start_point = location_feat.geometry().asPoint()
            elif str(location_feat["Haara"]) == data_feat["direction"][1]:
                end_point = location_feat.geometry().asPoint()

        if start_point and end_point:
            middle_point = calculate_middle_point(
                start_point, end_point, data_feat.geometry().asPoint()
            )

            feat = QgsFeature(result_layer.fields())
            feat.setGeometry(
                QgsGeometry.fromPolylineXY([start_point, middle_point, end_point])
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
