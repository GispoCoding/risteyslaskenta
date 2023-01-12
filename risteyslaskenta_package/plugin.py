from typing import Callable, List, Optional

from qgis.core import QgsCoordinateReferenceSystem, QgsWkbTypes
from qgis.PyQt.QtCore import QCoreApplication, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QWidget
from qgis.utils import iface

from risteyslaskenta_package.qgis_plugin_tools.tools.custom_logging import (
    setup_logger,
    teardown_logger,
)
from risteyslaskenta_package.qgis_plugin_tools.tools.i18n import setup_translation
from risteyslaskenta_package.qgis_plugin_tools.tools.resources import plugin_name

from .risteyslaskenta_functions import (
    convert_polygons_to_centroids,
    create_result_layer,
    process_intersection,
)
from .ui.risteyslaskenta_dialog import RisteyslaskentaDialog


class Plugin:
    """QGIS Plugin Implementation."""

    name = plugin_name()

    def __init__(self) -> None:
        setup_logger(Plugin.name)

        # initialize locale
        _, file_path = setup_translation()
        if file_path:
            self.translator = QTranslator()
            self.translator.load(file_path)
            # noinspection PyCallByClass
            QCoreApplication.installTranslator(self.translator)
        else:
            pass

        self.actions: List[QAction] = []
        self.menu = Plugin.name

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback: Callable,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: Optional[str] = None,
        whats_this: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> QAction:
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.

        :param text: Text that should be shown in menu items for this action.

        :param callback: Function to be called when the action is triggered.

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.

        :param parent: Parent widget for the new action. Defaults None.

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            iface.addToolBarIcon(action)

        if add_to_menu:
            iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self) -> None:  # noqa N802
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.add_action(
            "",
            text=Plugin.name,
            callback=self.run,
            parent=iface.mainWindow(),
            add_to_toolbar=False,
        )

    def onClosePlugin(self) -> None:  # noqa N802
        """Cleanup necessary items here when plugin dockwidget is closed"""
        pass

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            iface.removePluginMenu(Plugin.name, action)
            iface.removeToolBarIcon(action)
        teardown_logger(Plugin.name)

    def run(self) -> None:
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load
        # when the plugin is started
        self.first_start = True
        if self.first_start:
            self.first_start = False
            self.dlg = RisteyslaskentaDialog()

        # show the dialog and run dialog event loop
        self.dlg.show()
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:

            # Selections
            data_layer = self.dlg.mMapLayerComboBox.currentLayer()
            points_layer = self.dlg.mMapLayerComboBox_2.currentLayer()

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
            intersection_count = 0
            for intersection in intersections:
                if not process_intersection(
                    points_layer, data_layer, result_layer, intersection
                ):
                    failed_sum += 1
                intersection_count += 1
            print("Total number of intersections: {}".format(intersection_count))
            print(
                "Number of intersections without any location features: {}".format(
                    failed_sum
                )
            )

            result_layer.commitChanges()
            iface.vectorLayerTools().stopEditing(result_layer)
