# SylvaRoaD 
## Outil d'aide à la conception de nouvelles dessertes forestières 

Version : 0.2  
Langage : Python 3.x  

Financement : **Office National des Forêts - Pôle RDI de Chambéry** (*laurent.malabeux@onf.fr*)  
![ONF](./img/onf_logo.gif?raw=true)

Conception et développement : **Sylvain DUPIRE, SylvaLab - 2021** (*sylvain.dupire@sylvalab.fr*)   
![SylvaLab](./img/logo_sylvalab.png?raw=true)

---
### Contexte et objectif de SylvaRoaD

Les modèles numériques de terrain (MNT) dérivés de données spatiales à haute résolution (LiDAR, radar...) permettent aujourd'hui de représenter très fidèlement le relief. Cette représentation de qualité ouvre la porte à de nombreuses applications numériques pour faciliter le travail de terrain des forestiers, en particulier dans les zones les plus accidentées.

Dans le cadre de la conception de nouvelles dessertes forestières (route ou piste), ce type de MNT autorise l'utilisation d'algorithmes de recherche du meilleur itinéraire à la fois performants et précis.

SylvaRoaD s'inscrit dans cette logique et ambitionne d'aider les forestiers dans la conception de nouvelles dessertes forestières en leur permettant d'identifier un tracé optimal respectant plusieurs critères définis par l'utilisateur afin de desservir de nouvelles parcelles forestières. L'outil permet ainsi de tester rapidement plusieurs options d'itinéraires ou encore de rajouter des points de passages obligatoires. 
Les différents tracés ainsi identifiés peuvent être incorporés dans un GPS afin d'en valider la faisabilité sur le terrain.  

![SylvaLab](./img/illustration.png?raw=true)

Tags = ___Desserte___, ___forestière___, ___montagne___, ___route___, ___MNT___, ___tracé___, ___conception___, ___création___, ___Forest___, ___Road___, ___Design___, ___DTM___  

---  
### Données en entrée de SylvaRoaD

**Données spatiales obligatoires** :

- Modèle numérique de terrain (raster de préférence issu de données Lidar)
- Points de passage obligatoires (shapefile de points) incluant le départ et l'arrivée de l'itinéraire à concevoir et (optionnellement) des points de passages intermédiaires.

**Données spatiales optionnelles** :

- Un dossier contenant des couches d'obstacles (tous formats acceptés)
- Une couche décrivant le foncier et permettant de discriminer les parcelles où le tracé peut passer de celles où ce n'est pas le cas

**Paramètres de modélisation** :

- Pente en travers maximale
- Pente en travers maximale pour un virage en épingle
- Angle au-delà duquel un virage est considéré comme épingle
- Pente en long minimale
- Pente en long maximale
- Pénalité de changement de direction*
- Pénalité de changement de pente*
- Taille du voisinage de recherche*
- Différence d’altitude maximale entre le tracé et le terrain
- Longueur maximale cumulée où pente en travers > Pente en travers maximale


*Paramètres inspirés du plugin Qgis Forest Road Designer (<https://github.com/GobiernoLaRioja/forestroaddesigner/>).


### Données en sortie de SylvaRoaD

- Document rappelant les paramètres de modélisation ainsi que les résultats par tronçon testé
- Un polyligne (shapefile) par tronçon optimal identifié par le processus 
- Un polyligne (shapefile) où les lacets sont retracés par tronçon optimal identifié par le processus 
    
&nbsp;   
  

*ENGLISH VERSION*

# SylvaRoaD 
## Tool to assist in the design of new forest access routes 

Version : 0.2  
Language : Python 3.x

Funding : **Office National des Forêts - Pôle RDI de Chambéry** (*laurent.malabeux@onf.fr*)  
![ONF](./img/onf_logo.gif?raw=true)

Conception and developement : **Sylvain DUPIRE, SylvaLab - 2021** (*sylvain.dupire@sylvalab.fr*)   
![SylvaLab](./img/logo_sylvalab.png?raw=true)

---
### Context and Objective of SylvaRoaD

Digital terrain models (DTMs) derived from high-resolution spatial data (LiDAR, radar, etc.) now provide a very accurate representation of terrain. This high-quality representation opens the door to numerous digital applications to facilitate foresters' fieldwork, particularly in the most rugged areas.

When designing new forest access routes (roads or trails), this type of DTM allows the use of efficient and accurate route-finding algorithms.

SylvaRoaD is part of this approach and aims to assist foresters in the design of new forest access routes by enabling them to identify an optimal route that meets several user-defined criteria to serve new forest plots. The tool thus allows for the rapid testing of several route options or the addition of mandatory waypoints.

The various routes thus identified can be incorporated into a GPS in order to validate their feasibility on the ground. 

This plugin is a QGIS adaptation of the tool that can be found at: (<https://gitlab.com/SDupire/sylvaroad>)

![SylvaLab](./img/illustration.png?raw=true)

Tags = ___Forest___, ___Road___, ___Design___, ___DTM___  

---  
### SylvaRoaD Input Data

**Mandatory Spatial Data**:

- Digital terrain model (raster preferably from Lidar data)
- Mandatory waypoints (shapefile of points) including the start and end points of the route to be designed and (optionally) intermediate waypoints.

**Optional Spatial Data**:

- A folder containing obstacle layers (all formats accepted)
- A layer describing the land and allowing the distinction between parcels where the route can pass and those where it cannot

**Modeling Parameters**:

- Maximum cross slope
- Maximum cross slope for a hairpin turn
- Angle beyond which a turn is considered a hairpin turn
- Minimum longitudinal slope
- Maximum longitudinal slope
- Direction change penalty*
- Slope change penalty*
- Size of the search neighborhood*
- Maximum elevation difference between the route and the terrain
- Maximum cumulative length where cross slope > maximum cross slope


*Parameters inspired to the Qgis plugin "Forest Road Designer" (<https://github.com/GobiernoLaRioja/forestroaddesigner/>).


### SylvaRoaD output data

- Document detailing the modeling parameters and the results for each tested section
- One polyline (shapefile) for each optimal section identified by the process
- One polyline (shapefile) where the bends are traced for each optimal section identified by the process
 
    
&nbsp;   
  

  
---  


__Licence SylvaRoaD :__

    Copyright (C) 2021 by Sylvain DUPIRE - SylvaLab.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see https://www.gnu.org/licenses/
