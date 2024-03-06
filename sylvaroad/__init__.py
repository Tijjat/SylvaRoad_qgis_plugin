# -*- coding: utf-8 -*-
"""
/***************************************************************************
 sylvaroad
                                 A QGIS plugin
 This is an adaption of the SylvaRoad app for in qgis uses
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-03-05
        copyright            : (C) 2024 by Cosylval
        email                : yoann.zenner@viacesi.fr
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load sylvaroad class from file sylvaroad.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .SylvaRoad import sylvaroad
    return sylvaroad(iface)