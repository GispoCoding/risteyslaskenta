Development of risteyslaskenta plugin
===========================

This project uses [qgis_plugin_tools](https://github.com/GispoCoding/qgis_plugin_tools) submodule,
so when cloning use `--recurse-submodules` like so:
`git clone --recurse-submodules https://github.com/GispoCoding/risteyslaskenta.git`



The code for the plugin is in the [risteyslaskenta_package](../risteyslaskenta) folder. Make sure you have required tools, such as
Qt with Qt Editor and Qt Linquist installed by following this
[tutorial](https://www.qgistutorials.com/en/docs/3/building_a_python_plugin.html#get-the-tools).

For building the plugin use platform independent [build.py](../risteyslaskenta/build.py) script.

## Setting up development environment

To get started with the development, follow these steps:

1. Go to the  [risteyslaskenta_package](../risteyslaskenta) directory with a terminal
1. Create a new Python virtual environment with pre-commit using Python aware of QGIS libraries:
   ```shell
    python build.py venv
    ```
   In Windows it would be best to use python-qgis.bat or python-qgis-ltr.bat:
   ```shell
    C:\OSGeo4W64\bin\python-qgis.bat build.py venv
   ```
1. **Note: This part is  only for developers that are using QGIS < 3.16.8.** If you want to use IDE for development, it is best to start it with the
   following way on Windows:
   ```shell
    :: Check out the arguments with python build.py start_ide -h
    set QGIS_DEV_IDE=<path-to-your-ide.exe>
    set QGIS_DEV_OSGEO4W_ROOT=C:\OSGeo4W64
    set QGIS_DEV_PREFIX_PATH=C:\OSGeo4W64\apps\qgis-ltr
    C:\OSGeo4W64\bin\python-qgis.bat build.py start_ide
    :: If you want to create a bat script for starting the ide, you can do it with:
    C:\OSGeo4W64\bin\python-qgis.bat build.py start_ide --save_to_disk
   ```

Now the development environment should be all-set.

If you want to edit or disable some quite strict pre-commit scripts, edit .pre-commit-config.yaml.
For example to disable typing, remove mypy hook and flake8-annotations from the file.


## Deployment

Edit [build.py](../risteyslaskenta_package/build.py) *profile* variable to have the name of your QGIS profile you want the plugin to be deployed to. If you are running on Windows, make sure the value *QGIS_INSTALLATION_DIR* points to right folder

Run the deployment with:

```shell script
python build.py deploy
```

After deploying and restarting QGIS you should see the plugin in the QGIS installed plugins where you have to activate
it. Consider installing Plugin Reloader for easier development experience!


## Adding or editing source files

If you create or edit source files make sure that:

* they contain absolute imports:
    ```python
    from risteyslaskenta_package.utils.exceptions import TestException # Good

    from ..utils.exceptions import TestException # Bad

    ```
* they will be found by [build.py](../risteyslaskenta_package/build.py) script (`py_files` and `ui_files` values)

* you consider adding test files for the new functionality


### Local release

For local release install [qgis-plugin-ci](https://github.com/opengisch/qgis-plugin-ci) (possibly to different venv
to avoid Qt related problems on some environments) and follow these steps:
```shell
cd risteyslaskenta
qgis-plugin-ci package --disable-submodule-update 0.1.0
```
