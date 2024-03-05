# -*- coding: utf8 -*-
"""
Software: SylvaRoaD
File: SylvaRoaD_1_function.py
Copyright (C) Sylvain DUPIRE - SylvaLab 2021
Authors: Sylvain DUPIRE
Contact: sylvain.dupire@sylvalab.fr
Version: 2.2
Date: 2021/08/09
License :  GNU-GPL V3
"""

import numpy as np
import os,math,gc,datetime,sys
from osgeo import gdal,ogr,osr
import _heapq as heapq
from shapely import speedups
speedups.disable()
from shapely.geometry import LineString
from shapely.geometry import Point
import SylvaRoad_1_cython as cy

###############################################################################
### Function
###############################################################################
def conv_az_to_polar(az):
    return (360-(az-90))%360

def calculate_polar(x1,y1,x2,y2):
    """
    Calculate the azimuth between two points from their coordinates
    """
    DX = x2-x1
    DY = y2-y1
    Deuc = math.sqrt(DX**2+DY**2)
    if x2>x1:Fact=1
    else:Fact=-1
    Angle = math.degrees(math.acos(DY/Deuc))
    Angle *=Fact
    az = Angle%360
    return conv_az_to_polar(az)

def build_radius(R):
    coords =np.zeros((360,3),dtype=np.float) 
    for pol in range(0,360):
        coords[pol,0]=pol
        coords[pol,1]= R*math.cos(math.radians((pol)%360))#x
        coords[pol,2]= R*math.sin(math.radians((pol)%360))#y
    return coords

def diff_az(az_to,az_from):   
    if az_to>az_from:
        return min((360-(az_to-az_from),(az_to-az_from)))
    else:
        return min((360-(az_from-az_to),(az_from-az_to)))

def get_id_lacets(Path,angle_hairpin):
    id_lacet_classique = []    
    for i,pt in enumerate(Path[1:-1]):
        az1 = pt[3]
        az2 = Path[i+2,3]
        difangle1 = diff_az(az1,az2)
        if difangle1 > angle_hairpin:
            id_lacet_classique.append(i+1)   
            
    id_lacet_bis = [] 
    dif_angle = []
    for i,pt in enumerate(Path[1:-1]):
        if i in id_lacet_classique:
            continue
        if i-1 in id_lacet_classique:
            continue
        if i+1 in id_lacet_classique:
            continue
        if i+2 in id_lacet_classique:
            continue        
       
        if i+3<Path.shape[0]:
            az1 = pt[3]
            az2 = Path[i+2,3]
            difangle1 = diff_az(az1,az2)
            if abs((az2-difangle1)%360-az1)<0.1:
                difangle1*=-1
            az3 = Path[i+3,3]
            difangle2 = diff_az(az2,az3)
            if abs((az3-difangle2)%360-az2)<0.1:
                difangle2*=-1          
            
            if i in id_lacet_bis:                
                idx = id_lacet_bis.index(i)
                if dif_angle[idx]> abs(difangle1+difangle2):
                    continue
                else:
                    del dif_angle[idx],id_lacet_bis[idx]
                
            if i-1 in id_lacet_bis:
                idx = id_lacet_bis.index(i-1)
                if dif_angle[idx]> abs(difangle1+difangle2):
                    continue
                else:
                    del dif_angle[idx],id_lacet_bis[idx]
                
            if abs(difangle1+difangle2) > angle_hairpin:
                dif_angle.append(abs(difangle1+difangle2))
                id_lacet_bis.append(i+1)
                      
    lacets = np.zeros((len(id_lacet_bis)+len(id_lacet_classique),2),dtype=np.int32)
    lacets[:len(id_lacet_bis),0]=id_lacet_bis
    lacets[:len(id_lacet_bis),1]=2
    lacets[len(id_lacet_bis):,0]=id_lacet_classique
    lacets[len(id_lacet_bis):,1]=1
    ind = np.lexsort([lacets[:,1],lacets[:,0]])
    return lacets[ind]


def trace_lace(Path,R,Extent,Csize,angle_hairpin,dtm,coefplat=2):   
    
    lacets = get_id_lacets(Path,angle_hairpin)
    
    coords = build_radius(R)
    x0,y0=get_xy0(Extent,Csize)
    newPath = np.zeros((Path.shape[0],Path.shape[1]+3))
    newPath[:,0:7] = Path[:,0:7]
    for i,pt in enumerate(Path):
        newPath[i,9]=dtm[int(pt[0]),int(pt[1])]   
      
    Path=np.copy(newPath)
    Path[:,0]=y0-Path[:,0]*Csize
    Path[:,1]=Path[:,1]*Csize+x0 
    for lac in lacets:
        Path[lac[0],7]=lac[0]
        Path[lac[0],8]=lac[1]
            
    for lac in lacets: 
        line_lac,method = lac 
        try:
            line_lac=np.argwhere(Path[:,7]==line_lac)[0,0]             
        except:
            continue

        if method==1:
            #Angle > hairpin between 2 segments / Center at turn
            B = Point(Path[line_lac,1], Path[line_lac,0])
        else:
            #Angle > hairpin between 3 segments 
            #Center on the middle point of the segment
            A = Point(Path[line_lac,1], Path[line_lac,0])
            D = Point(Path[line_lac+1,1], Path[line_lac+1,0])           
            B = Point(0.5*A.x+0.5*D.x,0.5*A.y+0.5*D.y)            
         
        RingR15 = B.buffer(R*coefplat).boundary
        #find intersection before
        #A = Point(Path[line_lac-1,1], Path[line_lac-1,0])  
        cutpt_bef = 0
        check_int=False
        while not check_int and cutpt_bef*Csize<R*(coefplat+0.5):   
            cutpt_bef+=1
            vois = []
            for ide in range(max(0,line_lac-cutpt_bef),line_lac+1):
                vois.append(Point(Path[ide,1], Path[ide,0]))
            RoadBef = LineString(vois)
            check_int = RingR15.intersects(RoadBef)
            
        if check_int:
            intbef = RingR15.intersection(RoadBef)
            x1 = Point(intbef.coords[0]) 
            x,y = Path[line_lac-cutpt_bef+1,1],Path[line_lac-cutpt_bef+1,0]
            D = cy.Distplan(y, x, x1.y, x1.x)
            x1z = Path[line_lac-cutpt_bef+1,9]-Path[line_lac-cutpt_bef+1,2]/100*D
        else:                
            continue
                
        #find intersection after
        #C = Point(Path[line_lac+1,1], Path[line_lac+1,0])
        cutpt_aft = 0
        check_int=False
        while not check_int and cutpt_aft*Csize<R*(coefplat+0.5):   
            cutpt_aft+=1
            vois = []
            for ide in range(line_lac,min(Path.shape[0],line_lac+cutpt_aft+1)):
                vois.append(Point(Path[ide,1], Path[ide,0]))
            RoadAft = LineString(vois)
            check_int = RingR15.intersects(RoadAft)
            
        if check_int:
            intaft = RingR15.intersection(RoadAft)
            x2 = Point(intaft.coords[0])
            x,y = Path[line_lac+cutpt_aft,1],Path[line_lac+cutpt_aft,0]
            D = cy.Distplan(y, x, x2.y, x2.x)
            x2z = Path[line_lac+cutpt_aft,9]-Path[line_lac+cutpt_aft,2]/100*D
        else:                
            continue
        
        #get turn direction
        azfrom = Path[line_lac,3]
        azto = Path[line_lac+1,3]
        dif = diff_az(azfrom,azto)
        sign=1
        if abs((azto-dif)%360-azfrom)<0.1:
            sign*=-1
               
        #get point on radius                
        pol1 = calculate_polar(B.x,B.y,x1.x,x1.y)
        pol2 = calculate_polar(B.x,B.y,x2.x,x2.y)        
                  
        diff_angle = 360-diff_az(pol2,pol1)  
               
        nbpt = int(diff_angle/45.) 
        start = int(0.5*(360-(nbpt-1)*45-diff_az(pol2,pol1))+0.5)  
        pt_list = []
        pol = int((pol1+sign*start)%360+0.5)        
        xbef,ybef=x1.x,x1.y
        x,y=coords[pol,1]+B.x,coords[pol,2]+B.y
        D = []
        D.append(cy.Distplan(y, x, ybef,xbef))       
        pt_list.append([x,y])
        ybef,xbef=y,x
        for i in range(1,nbpt):            
            pol = int((pol1+i*sign*45+sign*start)%360)
            x,y=coords[pol,1]+B.x,coords[pol,2]+B.y
            pt_list.append([x,y])
            D.append(cy.Distplan(y, x, ybef,xbef))
            xbef,ybef=x,y
        D.append(cy.Distplan(x2.y, x2.x, ybef,xbef))
        Dcum=np.sum(D)  
        sl = (x2z-x1z) /  Dcum   
        newPath = np.zeros((Path.shape[0]+len(pt_list)+3-cutpt_bef-cutpt_aft,Path.shape[1]))
        newPath[0:line_lac-cutpt_bef+1]= Path[0:line_lac-cutpt_bef+1]
        newPath[line_lac-cutpt_bef+1,0:2] = x1.y,x1.x            
        newPath[line_lac-cutpt_bef+1,7:9] = lac[0],0
        newPath[line_lac-cutpt_bef+1,9] = x1z 
        newPath[line_lac-cutpt_bef+1,2] = Path[line_lac-cutpt_bef+1,2]
        for i,pt in enumerate(pt_list):
            newPath[line_lac-cutpt_bef+2+i,0:2]=pt[1],pt[0]
            newPath[line_lac-cutpt_bef+2+i,7:9] = lac[0],1
            newPath[line_lac-cutpt_bef+2+i,2] = sl*100
            newPath[line_lac-cutpt_bef+2+i,9] = x1z+sl*np.sum(D[:i+1])
        newPath[line_lac-cutpt_bef+3+i,0:2]=x2.y,x2.x
        newPath[line_lac-cutpt_bef+3+i,9]=x2z
        newPath[line_lac-cutpt_bef+3+i,2]=sl*100
        newPath[line_lac-cutpt_bef+3+i,7:9] = lac[0],1
        newPath[line_lac-cutpt_bef+4+i:]=Path[line_lac+cutpt_aft:] 
    
        Path=np.copy(newPath)
        
    
    #Complete table
    #Y X SLOPE AZ DPLAN D3D Z LSL
    #0 1 2     3  4     5   6 7
    keep = np.ones((Path.shape[0],),dtype=np.uint8)
    for i in range(1,Path.shape[0]):
        y,x = Path[i,0:2]
        y1,x1 = Path[i-1,0:2]
        Path[i,4]=math.sqrt((x1-x)**2+(y1-y)**2)
        if Path[i,4]!=0:
            Path[i,3]=calculate_azimut(x1,y1,x,y)  
        else:
            keep[i]=0
    tp = keep==1
    Path = Path[tp]    
    return Path
  
def check_field(filename,fieldname):    
    test=0
    source_ds = ogr.Open(filename)
    layer = source_ds.GetLayer()    
    ldefn = layer.GetLayerDefn()
    for n in range(ldefn.GetFieldCount()):
        fdefn = ldefn.GetFieldDefn(n)
        if fdefn.name==fieldname:
            test=1
            break
    if test:
        featureCount = layer.GetFeatureCount()
        vals = []
        for feat in layer:
            val = feat.GetField(fieldname)
            if val is not None:
                vals.append(feat.GetField(fieldname))
        source_ds.Destroy() 
        if len(vals)!=featureCount:
            test=2
    return test


def raster_get_info(in_file_name):
    source_ds = gdal.Open(in_file_name)    
    src_proj = osr.SpatialReference(wkt=source_ds.GetProjection())
    src_ncols = source_ds.RasterXSize
    src_nrows = source_ds.RasterYSize
    xmin,Csize_x,a,ymax,b,Csize_y = source_ds.GetGeoTransform()
    ymin = ymax+src_nrows*Csize_y
    nodata = source_ds.GetRasterBand(1).GetNoDataValue()
    names = ['ncols', 'nrows', 'xllcorner', 'yllcorner', 'cellsize','NODATA_value']
    values = [src_ncols,src_nrows,xmin,ymin,Csize_x,nodata]
    Extent = [xmin,xmin+src_ncols*Csize_x,ymin,ymax]
    return names,values,src_proj,Extent

#Chech all spatial entries before processing
def check_files(Dtm_file,Waypoints_file,Property_file):
    test = 1
    Csize = None
    mess="\nLES PROBLEMES SUIVANTS ONT ETE IDENTIFIES CONCERNANT LES ENTREES SPATIALES: \n"
    #Check DTM    
    try:
        names,values,proj,Extent = raster_get_info(Dtm_file)  
        Csize = values[4]
        if values[5]==None:           
            mess+=" -   Raster MNT : Aucune valeur de NoData definie. Attention, cela peut engendrer des résultats éronnés.\n" 
    except:
        test=0
        mess+=" -   Raster MNT :  Le chemin d'acces est manquant ou incorrect. Ce raster est obligatoire\n" 
            
    #Check Waypoints 
    try:    
        testfd = check_field(Waypoints_file,"ID_TRON")
        if testfd==0:
            test=0
            mess+=" -  Couche points de passage : Le champs 'ID_TRON' est manquant\n"  
        elif testfd==2:
            test=0
            mess+=" -  Couche points de passage : Veuillez remplir le champs 'ID_TRON' pour toutes les entités\n"         
        
        testfd =  check_field(Waypoints_file,"ID_POINT")
        if testfd==0:
            test=0
            mess+=" -  Couche points de passage : Le champs 'ID_POINT' est manquant\n"  
        elif testfd==2:
            test=0
            mess+=" -  Couche points de passage : Veuillez remplir le champs 'ID_POINT' pour toutes les entités\n"        
        
        testfd = check_field(Waypoints_file,"BUFF_POINT")
        if testfd==0:
            test=0
            mess+=" -  Couche points de passage : Le champs 'BUFF_POINT' est manquant\n"  
        elif testfd==2:
            test=0
            mess+=" -  Couche points de passage : Veuillez remplir le champs 'BUFF_POINT' pour toutes les entités\n"            
    except:
        test=0
        mess+=" -   Couche points de passage : Le chemin d'acces est manquant ou incorrect. Cette couche est obligatoire\n" 
    
    #Check foncier    
    if Property_file!="":   
        try:
            testfd = check_field(Property_file,"FONC_OK")
            if testfd==0:
                test=0
                mess+=" -  Couche foncier : Le champs 'FONC_OK' est manquant\n"  
            elif testfd==2:
                test=0
                mess+=" -  Couche foncier : Veuillez remplir le champs 'FONC_OK' pour toutes les entités\n"     
        except:
            test=0
            mess+=" -   Couche foncier : Le chemin d'acces est incorrect. \n" 
    if not test:
        mess+="\n"
        mess+="MERCI DE CORRIGER AVANT DE RELANCER L'OUTIL\n"
    return test,mess,Csize

def load_float_raster(raster_file):
    dataset = gdal.Open(raster_file,gdal.GA_ReadOnly)
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize    
    geotransform = dataset.GetGeoTransform()
    xmin = geotransform[0]
    xmax = xmin + geotransform[1]*cols
    ymax = geotransform[3]
    ymin = geotransform[3] + geotransform[5]*rows
    Extent = [xmin,xmax,ymin,ymax]
    Csize = abs(geotransform[1])
    proj = dataset.GetProjection()
    dataset_val = dataset.GetRasterBand(1)
    nodatavalue = dataset_val.GetNoDataValue()      
    Array = dataset_val.ReadAsArray()
    if nodatavalue is not None:
        Array[Array==nodatavalue]=-9999
    Array[np.isnan(Array)]=-9999
    dataset.FlushCache()
   
    return np.float_(Array),Extent,Csize,proj

def shapefile_to_np_array(file_name,Extent,Csize,attribute_name,order_field=None,order=None):
    """
    Convert shapefile to numpy array
    ----------
    Parameters
    ----------
    file_name:              string      Complete name of the shapefile to convert
    Extent:                 list        Extent of the array : [xmin,xmax,ymin,ymax]
    Csize:                  int, float  Cell resolution of the output array
    attribute_name:         string      Attribute name of the field used for rasterize
    order_field (optional): string      Attribute name of the field used to order the rasterization
    order (optional):       string      Sorting type : 'ASC' for ascending or 'DESC' descending

    Returns
    -------
    mask_array :            ndarray int32
    ----------
    Examples
    --------
    >>> import ogr,gdal
    >>> import numpy as np
    >>> mask_array = shapefile_to_np_array("Route.shp",[0,1000,0,2000],5,"Importance","Importance",'ASC')
    """
    #Recupere les dimensions du raster ascii
    xmin,xmax,ymin,ymax = Extent[0],Extent[1],Extent[2],Extent[3]
    nrows,ncols = int((ymax-ymin)/float(Csize)+0.5),int((xmax-xmin)/float(Csize)+0.5)
    # Get information from source shapefile
    orig_data_source = ogr.Open(file_name)
    source_ds = ogr.GetDriverByName("Memory").CopyDataSource(orig_data_source, "")
    source_layer = source_ds.GetLayer()
    if order:
        source_layer_ordered = source_ds.ExecuteSQL('SELECT * FROM '+str(source_layer.GetName())+' ORDER BY '+order_field+' '+order)
    else:source_layer_ordered=source_layer
    source_srs = source_layer.GetSpatialRef()
    # Initialize the new memory raster
    maskvalue = 1    
    xres=float(Csize)
    yres=float(Csize)
    geotransform=(xmin,xres,0,ymax,0, -yres)    
    target_ds = gdal.GetDriverByName('MEM').Create('', int(ncols), int(nrows), 1, gdal.GDT_Int32)
    target_ds.SetGeoTransform(geotransform)
    if source_srs:
        # Make the target raster have the same projection as the source
        target_ds.SetProjection(source_srs.ExportToWkt())
    else:
        # Source has no projection (needs GDAL >= 1.7.0 to work)
        target_ds.SetProjection('LOCAL_CS["arbitrary"]')
    # Rasterize
    err = gdal.RasterizeLayer(target_ds, [maskvalue], source_layer_ordered,options=["ATTRIBUTE="+attribute_name,"ALL_TOUCHED=TRUE"])
    if err != 0:
        raise Exception("error rasterizing layer: %s" % err)
    else:
        target_ds.FlushCache()
        mask_arr = target_ds.GetRasterBand(1).ReadAsArray()
        return mask_arr
  
def prepa_obstacle(Obstacles_directory,Extent,Csize,ncols,nrow):
    """
    Create raster with where there are obstacles, 0 anywhere else   
    """
    liste_file = os.listdir(Obstacles_directory)
    liste_obs = []
    for files in liste_file:
        if files[-4:len(files)]=='.shp':liste_obs.append(Obstacles_directory+files)
    if len(liste_obs)>0:
        Obstacles_skidder = shapefile_obs_to_np_array(liste_obs,Extent,Csize)        
    else: Obstacles_skidder = np.zeros((nrow,ncols),dtype=np.int8)
    return Obstacles_skidder

def shapefile_obs_to_np_array(file_list,Extent,Csize):
    """
    Create a numpy array from shapefile contained in a directory
    ----------
    Parameters
    ----------
    file_list:              string      List of .shp file to rasterize
    Extent:                 list        Extent of the area : [xmin,xmax,ymin,ymax]
    Csize:                  int, float  Cell resolution of the area  

    Returns
    -------
    mask_array :            ndarray int32
    """
    #Get raster dimension
    xmin,xmax,ymin,ymax = Extent[0],Extent[1],Extent[2],Extent[3]
    nrows,ncols = int((ymax-ymin)/float(Csize)+0.5),int((xmax-xmin)/float(Csize)+0.5)        
    #Create obstacle raster
    Obstacle = np.zeros((nrows,ncols),dtype=np.int)
    #Loop on all shaefile
    for shp in file_list:        
        # Get shapefile info
        source_ds = ogr.Open(shp)
        source_layer = source_ds.GetLayer()    
        source_srs = source_layer.GetSpatialRef()
        source_type = source_layer.GetGeomType()
        # Create copy
        target_ds1 = ogr.GetDriverByName("Memory").CreateDataSource("")
        layerName = os.path.splitext(os.path.split(shp)[1])[0]
        layer = target_ds1.CreateLayer(layerName, source_srs, source_type)
        layerDefinition = layer.GetLayerDefn()
        new_field = ogr.FieldDefn('Transfo', ogr.OFTInteger)
        layer.CreateField(new_field)
        ind=0
        for feat in source_layer:
            geometry = feat.GetGeometryRef()
            feature = ogr.Feature(layerDefinition)
            feature.SetGeometry(geometry)
            feature.SetFID(ind)
            feature.SetField('Transfo',1)
            # Save feature
            layer.CreateFeature(feature)
            # Cleanup
            feature.Destroy()
            ind +=1
        # Initialize raster
        maskvalue = 1    
        xres=float(Csize)
        yres=float(Csize)
        geotransform=(xmin,xres,0,ymax,0, -yres)         
        target_ds = gdal.GetDriverByName('MEM').Create('', int(ncols), int(nrows), 1, gdal.GDT_Int32)
        target_ds.SetGeoTransform(geotransform)
        if source_srs:
            # Make the target raster have the same projection as the source
            target_ds.SetProjection(source_srs.ExportToWkt())
        else:
            # Source has no projection (needs GDAL >= 1.7.0 to work)
            target_ds.SetProjection('LOCAL_CS["arbitrary"]')
        # Rasterize
        err = gdal.RasterizeLayer(target_ds, [maskvalue], layer,options=["ATTRIBUTE=Transfo","ALL_TOUCHED=TRUE"])
        if err != 0:
            raise Exception("error rasterizing layer: %s" % err)
        else:
            target_ds.FlushCache()
            mask_arr = target_ds.GetRasterBand(1).ReadAsArray()
        Obstacle = Obstacle + mask_arr
        target_ds1.Destroy()
        source_ds.Destroy()
    Obstacle = np.int8(Obstacle>0)
    return Obstacle

def get_proj_from_road_network(road_network_file):
    source_ds = ogr.Open(road_network_file)
    source_layer = source_ds.GetLayer()    
    source_srs = source_layer.GetSpatialRef()
    return source_srs.ExportToWkt(),source_srs

 
def Path_to_lineshape(Path,Line_Shape_Path,projection,Extent,Csize,dtm,nb_lac):
    """
    Convert a file of point coordinate to a line shapefile
    ----------
    Parametres
    ----------
    point_coords:     ndarray float    Matrix contenaing positiosn X Y and line ID
    Line_Shape_Path:  string           Complete name of the output shapefile containing lines
    projection:       string           Spatial projection 

    Examples
    --------
    >>> import ogr,gdal
    >>> points_to_lineshape(point_coords,"Line.shp",projection)
    """
    x0,y0=get_xy0(Extent,Csize)
    #Recupere le driver
    driver = ogr.GetDriverByName('ESRI Shapefile')
    # Create output line shapefile 
    if os.path.exists(Line_Shape_Path):driver.DeleteDataSource(Line_Shape_Path)
    target_ds = driver.CreateDataSource(Line_Shape_Path)
    layerName = os.path.splitext(os.path.split(Line_Shape_Path)[1])[0]
    layer = target_ds.CreateLayer(layerName, projection, ogr.wkbLineString)
    layerDefinition = layer.GetLayerDefn()   
    new_field = ogr.FieldDefn('ID_SEG', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('X_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Y_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Z_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('X_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Y_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Z_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('LPLAN_SEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('LPLAN_CUM', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L3D_SEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L3D_CUM', ogr.OFTReal)
    layer.CreateField(new_field)   
    new_field = ogr.FieldDefn('PENTE_LONG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('AZI_DEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('AZI_GRAD', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('DELTA_Z', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L_PTSUPMAX', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L_PLAT', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('PT_AMONT', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('PT_AVAL', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('P_ROCHER', ogr.OFTInteger)
    layer.CreateField(new_field)
    if nb_lac==0:
        new_field = ogr.FieldDefn('METHOD', ogr.OFTInteger)
        layer.CreateField(new_field)
    nbpts = Path.shape[0]
    ind=0
    point_coords = np.int32(Path[:,0:2])
    prev_L,L3Dcum = 0,0
    while ind<nbpts-1: 
        line = ogr.Geometry(ogr.wkbLineString)
        yS,xS = point_coords[ind]
        yE,xE = point_coords[ind+1]
        yrS,xrS = y0-yS*Csize,xS*Csize+x0
        yrE,xrE = y0-yE*Csize,xE*Csize+x0
        line.AddPoint(xrS,yrS)
        line.AddPoint(xrE,yrE)
        feature = ogr.Feature(layerDefinition)
        feature.SetGeometry(line)
        feature.SetFID(ind)
        feature.SetField('ID_SEG',ind+1)
        feature.SetField('X_DEB',xrS)
        feature.SetField('Y_DEB',yrS)
        feature.SetField('Z_DEB',dtm[yS,xS])
        feature.SetField('X_FIN',xrE)
        feature.SetField('Y_FIN',yrE)
        feature.SetField('Z_FIN',dtm[yE,xE])
        Lcum = Path[ind+1,4]
        D = Lcum-prev_L       
        feature.SetField('LPLAN_SEG',D)
        feature.SetField('LPLAN_CUM',Lcum)
        prev_L = Lcum
        dZ = dtm[yE,xE]-dtm[yS,xS]
        L3D = math.sqrt(dZ**2+D**2)
        L3Dcum+=L3D
        feature.SetField('L3D_SEG',L3D)
        feature.SetField('L3D_CUM',L3Dcum)
        feature.SetField('PENTE_LONG',Path[ind+1,2])
        feature.SetField('L_PTSUPMAX',Path[ind+1,6])
        feature.SetField('AZI_DEG',Path[ind+1,3])
        feature.SetField('AZI_GRAD',round(Path[ind+1,3]*20/18.,1))
        feature.SetField('DELTA_Z',dZ) 
        if nb_lac==0:
            feature.SetField('METHOD',0) 
        layer.CreateFeature(feature)
        line.Destroy()
        feature.Destroy()
        ind +=1        

    target_ds.Destroy() 
    
    
def NewPath_to_lineshape(Path,Line_Shape_Path,projection):
    """
    Convert a file of point coordinate to a line shapefile
    ----------
    Parametres
    ----------
    point_coords:     ndarray float    Matrix contenaing positiosn X Y and line ID
    Line_Shape_Path:  string           Complete name of the output shapefile containing lines
    projection:       string           Spatial projection 

    Examples
    --------
    >>> import ogr,gdal
    >>> points_to_lineshape(point_coords,"Line.shp",projection)
    """   
    #Recupere le driver
    driver = ogr.GetDriverByName('ESRI Shapefile')
    # Create output line shapefile 
    if os.path.exists(Line_Shape_Path):driver.DeleteDataSource(Line_Shape_Path)
    target_ds = driver.CreateDataSource(Line_Shape_Path)
    layerName = os.path.splitext(os.path.split(Line_Shape_Path)[1])[0]
    layer = target_ds.CreateLayer(layerName, projection, ogr.wkbLineString)
    layerDefinition = layer.GetLayerDefn()   
    new_field = ogr.FieldDefn('ID_SEG', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('X_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Y_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Z_DEB', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('X_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Y_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('Z_FIN', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('LPLAN_SEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('LPLAN_CUM', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L3D_SEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L3D_CUM', ogr.OFTReal)
    layer.CreateField(new_field)   
    new_field = ogr.FieldDefn('PENTE_LONG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('AZI_DEG', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('AZI_GRAD', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('DELTA_Z', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L_PTSUPMAX', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('METHOD', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('L_PLAT', ogr.OFTReal)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('PT_AMONT', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('PT_AVAL', ogr.OFTInteger)
    layer.CreateField(new_field)
    new_field = ogr.FieldDefn('P_ROCHER', ogr.OFTInteger)
    layer.CreateField(new_field)    
    nbpts = Path.shape[0]
    ind=0
    point_coords = Path[:,0:2]
    Lcum,L3Dcum=0,0
    while ind<nbpts-1: 
        line = ogr.Geometry(ogr.wkbLineString)
        yrS,xrS = point_coords[ind]
        yrE,xrE = point_coords[ind+1]
        line.AddPoint(float(xrS),float(yrS))
        line.AddPoint(float(xrE),float(yrE))
        feature = ogr.Feature(layerDefinition)
        feature.SetGeometry(line)
        feature.SetFID(ind)
        feature.SetField('METHOD',Path[ind+1,8])
        feature.SetField('ID_SEG',ind+1)
        feature.SetField('X_DEB',float(xrS))
        feature.SetField('Y_DEB',float(yrS))
        feature.SetField('Z_DEB',float(Path[ind,9]))
        feature.SetField('X_FIN',float(xrE))
        feature.SetField('Y_FIN',float(yrE))
        feature.SetField('Z_FIN',float(Path[ind+1,9]))
        dZ = Path[ind+1,9]-Path[ind,9]
        L3D = math.sqrt(dZ**2+Path[ind+1,4]**2)
        L3Dcum+=L3D   
        Lcum += Path[ind+1,4]
        feature.SetField('LPLAN_SEG',float(Path[ind+1,4]))
        feature.SetField('LPLAN_CUM',float(Lcum))
        feature.SetField('L3D_SEG',float(L3D))
        feature.SetField('L3D_CUM',float(L3Dcum))
        feature.SetField('PENTE_LONG',float(Path[ind+1,2]))
        feature.SetField('L_PTSUPMAX',float(Path[ind+1,6]))
        feature.SetField('AZI_DEG',float(Path[ind+1,3]))
        feature.SetField('AZI_GRAD',float(round(Path[ind+1,3]*20/18.,1)))
        feature.SetField('DELTA_Z',float(dZ))
        layer.CreateFeature(feature)
        line.Destroy()
        feature.Destroy()
        ind +=1        

    target_ds.Destroy()  

   
def reconstruct_path(goal, start, Best,Tab_corresp):    
    current = goal
    path = []
    while current != start:
        path.append([Tab_corresp[current,0],Tab_corresp[current,1],Best[current,3],
                     Best[current,4],Best[current,2],Best[current,1],Best[current,7]])
        current = int(Best[current,5])
    path.append([Tab_corresp[current,0],Tab_corresp[current,1],-1,-1,0,0,0]) # optional
    path.reverse() # optional
    return np.array(path)


def calculate_azimut(x1,y1,x2,y2):
    """
    Calculate the azimuth between two points from their coordinates
    """
    DX = x2-x1
    DY = y2-y1
    Deuc = math.sqrt(DX**2+DY**2)
    if x2>x1:Fact=1
    else:Fact=-1
    Angle = math.degrees(math.acos(DY/Deuc))
    Angle *=Fact
    return Angle%360

class PriorityQueue:
    def __init__(self):
        self.elements = []
    
    def empty(self):
        return len(self.elements) == 0    
   
    def put(self, item, theo_d,d_to_end):
        heapq.heappush(self.elements, (theo_d,d_to_end, item))
        
    def get(self):
        return heapq.heappop(self.elements)[2]     

class PriorityQueue2:
    def __init__(self):
        self.elements = []
    
    def empty(self):
        return len(self.elements) == 0
    
    def put(self, item, theo_d,d_to_end,angle_max):
        heapq.heappush(self.elements, (theo_d,d_to_end,angle_max, item))
    
    def get(self):
        return heapq.heappop(self.elements)[2:4] 


def build_NeibTable(D_neighborhood,Csize,dtm,Obs,min_slope,max_slope):
    nbpix_neighborhood=int(D_neighborhood/Csize+0.5)
    x, y = np.meshgrid(np.arange(-nbpix_neighborhood, nbpix_neighborhood+1, dtype=np.int), 
                      np.arange(-nbpix_neighborhood, nbpix_neighborhood+1, dtype=np.int))
    coords = np.vstack((np.ndarray.flatten(x), np.ndarray.flatten(y))).T    
    coords = np.delete(coords, [nbpix_neighborhood*(2*nbpix_neighborhood+2)],axis=0)
    azimuts = np.copy(coords[:,0])*0.
    for i,neig in enumerate(coords):
        azimuts[i]=calculate_azimut(0,0,neig[1],-neig[0])
    dists_index = np.sqrt(np.sum(np.square(coords),axis=1))*Csize
    
    #keep only neibourg within distance
    tp = dists_index <= D_neighborhood
    coords=coords[tp]
    azimuts=np.float32(azimuts[tp])
    dists_index=np.float32(dists_index[tp])
    
    IdVois, Id, Tab_corresp,IdPix ,Slope = cy.build_Tab_neibs(Obs,dtm,azimuts,
                                                              dists_index,coords,
                                                              min_slope,max_slope,
                                                              np.sum(Obs==0))
    
    nbneibmax = np.max(Tab_corresp[:,2])
    return IdVois[:,:nbneibmax],Id[:,:nbneibmax],Tab_corresp,IdPix,Slope[:,:nbneibmax],dists_index,azimuts
    

def Astar_force_wp(segments,Slope,IdVois, Id, Tab_corresp,IdPix,Az,Dist,
                   min_slope,max_slope,penalty_xy,penalty_z,Dist_to_End,
                   Local_Slope,Perc_Slope,Csize,dtm,max_diff_z,
                   trans_slope_all,newObs,angle_hairpin,Lmax_ab_sl,Radius,
                   D_neighborhood,prop_sl_max=0.25,max_slope_hairpin=10,tal=1.5):
    
    #1. Create neighborhood matrix with azimut and distance 
    nrows,ncols=Dist_to_End.shape
    nbpart = len(segments)
    test=1
    FullPath = []  
    max_slope_change = 2.*max(min_slope,max_slope) 
    max_hairpin_angle = 180-max_slope_hairpin*0.01/tal*180*(1+1/(2*math.pi))
    Dmin = (180-max_hairpin_angle)*2*math.pi*2*Radius/360. 
    Obs2 = np.int8(Perc_Slope>trans_slope_all)
    
    nbpix = Tab_corresp.shape[0]    
    Best = np.zeros((nbpix,11),dtype=np.float32) 
    Best[:,0]=-1
    Best[:,6]=-1
    Best[:,1]=10000000    
    idseg=0
    seg = segments[0]
    yS,xS = seg[0]   
    Dtocp = Dist_to_End[yS,xS]
    max_nbptbef=max(int(D_neighborhood/Csize),7)  
    
    #idcel cost_so_far Dplan Slope_from az_from came_from hairpin_from Lsl idseg Dtocp ishairpin
    #0     1           2     3          4       5         6            7   8     9     10              
     
    for idseg,seg in enumerate(segments):    
        if not test:
            break
        yS,xS = seg[0]
        yE,xE = goal= seg[1]
        bufgoal = 0
        if idseg==nbpart-1:
            bufgoal = seg[2]
     
        idcel = IdPix[yS,xS]
        if Best[idcel,0]<0:            
            Best[idcel]=idcel,0,0,0,-1,-1,0,0,0,Dist_to_End[yS,xS],0
     
        idend = IdPix[yE,xE]
        #2. initiate search          
        #frontier = PriorityQueue()
        frontier = PriorityQueue()
        #frontier.put(start, Dist_to_End[yS,xS],Dist_to_End[yS,xS]) 
        frontier.put(idcel, Dist_to_End[yS,xS],Dist_to_End[yS,xS])               
           
        str_process = " %"
        test=0
        loop=0
        mindist_to_end = 10000000
        
        closetogoal = PriorityQueue2()        
        key_frontier= {}
                    
        if segments[-1][1]==goal:
            take_dtoend = 1
            Dtocp = Dist_to_End[yS,xS]
        else:
            take_dtoend = 0
            Dtocp = cy.Distplan(yS,xS,yE,xE)*Csize  
        
        #3. search best path   
        while not frontier.empty() and not test:
            av = int(100*(1-mindist_to_end/Dtocp))   
            if loop>0:        
                sys.stdout.write("\r    Segment "+str(idseg+1)+" - Progression %d" % av + str_process)
                sys.stdout.flush()                 
            
            idcurrent = frontier.get()   
                              
           
            if idcurrent == idend:
                test=1
                break
            
            nbptbef = Best[idcurrent,8]
            if nbptbef==0:
                Best,add_to_frontier,mindist_to_end=cy.calc_init(idcurrent,Id,IdVois,Slope,
                                                                 Best,Tab_corresp,Az,Dist,
                                                                 newObs,Obs2,Dist_to_End,dtm,            
                                                                 Csize,max_diff_z,D_neighborhood,Lmax_ab_sl,
                                                                 take_dtoend,yE,xE,mindist_to_end)
                
            
            else:
                yc,xc =Tab_corresp[idcurrent,0], Tab_corresp[idcurrent,1] 
                Dist_current_goal = cy.Distplan(yc,xc,yE,xE)*Csize      
                if Dist_current_goal<=bufgoal: 
                    prev = int(Best[idcurrent,5])
                    difangle = cy.diff_az(Best[prev,4],Best[idcurrent,4])
                    penalty_dir = penalty_xy*(difangle/angle_hairpin)**2
                    prev2 = int(Best[prev,5])
                    difangle2 = cy.diff_az(Best[prev2,4],Best[prev,4])
                    penalty_dir += penalty_xy*(difangle2/angle_hairpin)**2
                    closetogoal.put(idcurrent,
                                    Dist_current_goal+penalty_dir,
                                    Dist_current_goal,
                                    max(difangle,difangle2))
                
                Best,add_to_frontier,mindist_to_end = cy.basic_calc(idcurrent,Id,IdVois,Slope,
                                                                    Best,Tab_corresp,Az,Dist,
                                                                    newObs,Obs2,Dist_to_End,dtm,Local_Slope[yc,xc]/100.,           
                                                                    Csize,max_diff_z,D_neighborhood,Lmax_ab_sl,
                                                                    take_dtoend,yE,xE,mindist_to_end,prop_sl_max,
                                                                    angle_hairpin,Radius,penalty_xy,penalty_z,
                                                                    max_slope_change,max_hairpin_angle,Dmin,max_nbptbef)
                
            for idvois in add_to_frontier:                 
                theo_d = round(Best[idvois,1]+Best[idvois,9],1)
                dtocp = round(Best[idvois,9],1)
                if (idvois,theo_d,dtocp) not in key_frontier:
                    frontier.put(idvois,theo_d,dtocp)  
                    key_frontier[(idvois,theo_d,dtocp) ]=1    
                
            loop+=1 
            # print(loop)              
                   
        #4. reconstruct path
        Path=None
        if test or not closetogoal.empty():
            if not test:
                angle,idclosest= closetogoal.get()
                yE,xE=Tab_corresp[int(idclosest),0],Tab_corresp[int(idclosest),1]            
            Path =reconstruct_path(IdPix[yE,xE], IdPix[yS,xS], Best,Tab_corresp) 
            FullPath.append(Path)
            print("\n    Point de passage ID_POINT "+str(idseg+2)+" atteind")
        else:
            print("\n    Impossible d'atteindre le Point de passage ID_POINT "+str(idseg+2))
                    
    Path=None
    if len(FullPath)>0:
        nb = 1
        for por in FullPath: 
            nb+=por.shape[0]           
        Path = np.zeros((nb-1,7))
        idline=FullPath[0].shape[0]
        Path[0:idline]=FullPath[0] 
        for i in range(1,len(FullPath)):            
            idline2=FullPath[i].shape[0]-1
            Path[idline:idline+idline2]=FullPath[i][1:]
            idline+=idline2            
        Path=Path[:idline] 
        Path[1:,-1]-=Path[:-1,-1]
        
    return Path,test

def Astar_buf_wp(segments,Slope,IdVois, Id, Tab_corresp,IdPix,Az,Dist,
                 min_slope,max_slope,penalty_xy,penalty_z,Dist_to_End,
                 Local_Slope,Perc_Slope,Csize,dtm,max_diff_z,
                 trans_slope_all,newObs,angle_hairpin,Lmax_ab_sl,Radius,
                 D_neighborhood,prop_sl_max=0.25,tal=1.5,lpla=4):
    
    #1. Create neighborhood matrix with azimut and distance 
    nrows,ncols=Dist_to_End.shape
    nbpart = len(segments)
    test=1    
    max_slope_change = 2.*max(min_slope,max_slope) 
    max_slope_hairpin= max_slope*0.5+2 #From observation on previous simulation
    max_hairpin_angle = 180-max_slope_hairpin*0.01/tal*180*(1+1/(2*math.pi)) #Distance on the slope between roads
    max_hairpin_angle -= lpla*360/(2*math.pi*2*Radius)#Additional Distance corresponding to platform width
    Dmin = (180-max_hairpin_angle)*2*math.pi*2*Radius/360. 
    Obs2 = np.int8(Perc_Slope>trans_slope_all)
    
    nbpix = Tab_corresp.shape[0]    
    Best = np.zeros((nbpix,11),dtype=np.float32) 
    Best[:,0]=-1
    Best[:,6]=-1
    Best[:,1]=10000000  
    Best[:,9]=10000000  
    idseg=0
    seg = segments[0]
    yS,xS = seg[0]   
    Dtocp = Dist_to_End[yS,xS]
    max_nbptbef=max(int(D_neighborhood/Csize),7)  
    
    #idcel cost_so_far Dplan Slope_from az_from came_from hairpin_from Lsl idseg Dtocp ishairpin 
    #0     1           2     3          4       5         6            7   8     9     10              
     
    seg= segments[0]
    yI,xI = seg[0]
    idStart = IdPix[yI,xI]
    Best[idStart]=idStart,0,0,0,-1,-1,0,0,0,Dist_to_End[yI,xI],0
    frontier = PriorityQueue()
    key_frontier= {}
    frontier.put(idStart, Dist_to_End[yI,xI],Dist_to_End[yI,xI]) 
    difbuf = 0   
    Dcheck = min(400,Dtocp)
    
    for idseg,seg in enumerate(segments):    
        if not test:
            break
        yS,xS = seg[0]
        yE,xE = goal= seg[1]        
        bufgoal = max(0,seg[2])  
        idend = IdPix[yE,xE]
        
        #2. initiate search   
        str_process = " %"
        test=0
        loop=0
        mindist_to_end = 10000000
        min_cost=10000000
        prev_cost = 0
        add_cost = min(max(20*bufgoal,10*max(penalty_xy,penalty_z))+difbuf,max(difbuf,4000))
                                 
        if segments[-1][1]==goal:
            take_dtoend = 1
            Dtocp = Dist_to_End[yS,xS]
        else:
            take_dtoend = 0
            Dtocp = cy.Distplan(yS,xS,yE,xE)*Csize  
        
        endreach = 0
        
        #3. search best path   
        while not frontier.empty() and prev_cost<min_cost:
            av = min(int(100*(1-mindist_to_end/Dtocp)),99)                     
            if loop>0:        
                sys.stdout.write("\r    Segment "+str(idseg+1)+" - Progression %d" % av + str_process)
                sys.stdout.flush()                 
            
            idcurrent = frontier.get()  
            prev_cost=Best[idcurrent,1]
            if idcurrent==idend:
                min_cost=Best[idend,1]+add_cost
                endreach = 1
            
            if endreach:
                if cy.Distplan(Tab_corresp[idcurrent,0],Tab_corresp[idcurrent,1],yE,xE)*Csize > Dcheck:
                    continue
            
            nbptbef = Best[idcurrent,8]
            if nbptbef==0:
                Best,add_to_frontier,mindist_to_end=cy.calc_init(idcurrent,Id,IdVois,Slope,
                                                                 Best,Tab_corresp,Az,Dist,
                                                                 newObs,Obs2,Dist_to_End,dtm,            
                                                                 Csize,max_diff_z,D_neighborhood,Lmax_ab_sl,
                                                                 take_dtoend,yE,xE,mindist_to_end)
                
            
            else:
                yc,xc =Tab_corresp[idcurrent,0], Tab_corresp[idcurrent,1]                 
                Best,add_to_frontier,mindist_to_end = cy.basic_calc(idcurrent,Id,IdVois,Slope,
                                                                    Best,Tab_corresp,Az,Dist,
                                                                    newObs,Obs2,Dist_to_End,dtm,Local_Slope[yc,xc]/100.,           
                                                                    Csize,max_diff_z,D_neighborhood,Lmax_ab_sl,
                                                                    take_dtoend,yE,xE,mindist_to_end,prop_sl_max,
                                                                    angle_hairpin,Radius,penalty_xy,penalty_z,
                                                                    max_slope_change,max_hairpin_angle,Dmin,max_nbptbef)    
                
            for idvois in add_to_frontier:                 
                theo_d = round(Best[idvois,1]+Best[idvois,9],1)
                dtocp = round(Best[idvois,9],1)
                if (idvois,theo_d,dtocp) not in key_frontier:
                    frontier.put(idvois,theo_d,dtocp)  
                    key_frontier[(idvois,theo_d,dtocp) ]=1    
                
            loop+=1       
        
        av=100
        sys.stdout.write("\r    Segment "+str(idseg+1)+" - Progression %d" % av + str_process)
        sys.stdout.flush()   
        
        #4. Identify pixels within bufgoal and add them to new search               
        if idseg<nbpart-1:
            #There is a segment after
            yE,xE=segments[idseg+1][1]        
        Best,add_to_frontier,keep = cy.get_pix_bufgoal_and_update(Best,Tab_corresp,
                                                                  bufgoal,idStart,
                                                                  Csize,yE, xE)        
        nbok = add_to_frontier.shape[0]
        #5. Check if checkpoint is reached
        test=1
        if nbok==0:
            test=0
            print("\n     - Impossible d'atteindre le Point de passage ID_POINT "+str(idseg+2))
            break            
        tp = keep==0
        Best[tp]=0        
        Best[tp,0]=-1
        Best[tp,6]=-1
        Best[tp,1]=10000000 
        Best[tp,9]=10000000 
        
        
        #6.a if not last segment
        print("\n     - Point de passage ID_POINT "+str(idseg+2)+" atteind")
        if idseg<nbpart-1:   
            difbuf = np.max(Best[add_to_frontier,1])-np.min(Best[add_to_frontier,1])
            key_frontier= {}
            frontier = PriorityQueue()
            for idvois in add_to_frontier:                 
                theo_d = round(Best[idvois,1],1)
                dtocp = round(Best[idvois,9],1)
                if (idvois,theo_d,dtocp) not in key_frontier:
                    frontier.put(idvois,theo_d,dtocp)  
                    key_frontier[(idvois,theo_d,dtocp) ]=1  
        #6.b if last segment 
        else:
            if nbok>1:            
                Buf = Best[add_to_frontier]              
                ind = np.lexsort([-Buf[:,6],Buf[:,9]])
                goal = int(Buf[ind][0][0])
            else:
                goal = add_to_frontier[0]
                                     
    #Reconstruct path                
    Path=None
    if test:        
        Path =reconstruct_path(goal, idStart, Best,Tab_corresp)
        Path[1:,-1]-=Path[:-1,-1]  
    else:
        ind = np.argmin(Best[:,9])
        Path =reconstruct_path(ind, idStart, Best,Tab_corresp)
        Path[1:,-1]-=Path[:-1,-1]  
        
    return Path,test

def get_xy0(Extent,Csize):   
    return Extent[0]+0.5*Csize,Extent[3]-0.5*Csize

def get_Slope(Dtm_file):
    a=gdal.DEMProcessing('slope', Dtm_file, 'slope',slopeFormat="percent",computeEdges=True,format='MEM')
    return a.GetRasterBand(1).ReadAsArray()

def create_res_dir(Result_Dir,
                   trans_slope_all,trans_slope_hairpin,
                   min_slope,max_slope,
                   penalty_xy,penalty_z,
                   D_neighborhood):
    dirs = [d for d in os.listdir(Result_Dir) if os.path.isdir(os.path.join(Result_Dir, d))]
    list_dir = []
    for dire in dirs:
        if dire[:5]=='Simu_':
            list_dir.append(dire)
    optnum = len(list_dir)+1
    Rspace=Result_Dir+'Simu_'+str(optnum)    
    Rspace+="_Pl("+str(min_slope)+"-"+str(max_slope)+")"
    Rspace+="_Pt("+str(trans_slope_all)+"-"+str(trans_slope_hairpin)+")"
    Rspace+="_Pen("+str(penalty_xy)+"-"+str(penalty_z)+")"
    Rspace+="_D("+str(D_neighborhood)+")"
    try:os.mkdir(Rspace)
    except:pass   
    return Rspace+'/'


def heures(Hdebut,language):
    Hfin = datetime.datetime.now()
    duree = Hfin - Hdebut
    ts = duree.seconds
    nb_days = int(ts/3600./24.)
    ts -= nb_days*3600*24
    nb_hours = int(ts/3600)
    ts -= nb_hours*3600
    nb_minutes = int(ts/60)
    ts -= nb_minutes*60  
    if nb_days>0:
        if language=='FR': 
            str_duree = str(nb_days)+'j '+str(nb_hours)+'h '+str(nb_minutes)+'min '+str(ts)+'s'
        else:
            str_duree = str(nb_days)+'d '+str(nb_hours)+'h '+str(nb_minutes)+'min '+str(ts)+'s'
    elif nb_hours >0:
        str_duree = str(nb_hours)+'h '+str(nb_minutes)+'min '+str(ts)+'s'
    elif nb_minutes>0:
        str_duree = str(nb_minutes)+'min '+str(ts)+'s'
    else:
        str_duree = str(ts)+'s'        
    if language=='FR':
        str_debut = str(Hdebut.day)+'/'+str(Hdebut.month)+'/'+str(Hdebut.year)+' '+str(Hdebut.hour)+':'+str(Hdebut.minute)+':'+str(Hdebut.second)
        str_fin = str(Hfin.day)+'/'+str(Hfin.month)+'/'+str(Hfin.year)+' '+str(Hfin.hour)+':'+str(Hfin.minute)+':'+str(Hfin.second)
    else:
        str_debut = str(Hdebut.year)+'/'+str(Hdebut.month)+'/'+str(Hdebut.day)+' '+str(Hdebut.hour)+':'+str(Hdebut.minute)+':'+str(Hdebut.second)
        str_fin = str(Hfin.year)+'/'+str(Hfin.month)+'/'+str(Hfin.day)+' '+str(Hfin.hour)+':'+str(Hfin.minute)+':'+str(Hfin.second)
    return str_duree,str_fin,str_debut

def get_param(trans_slope_all,trans_slope_hairpin,
              min_slope,max_slope,
              penalty_xy,penalty_z,
              D_neighborhood,max_diff_z,angle_hairpin,
              Dtm_file,Obs_Dir,Waypoints_file,
              Property_file,Csize,Lmax_ab_sl,Radius):
    
    txt = "FICHIERS UTILISES POUR LA MODELISATION:\n\n"
    txt = txt+"   - MNT :                   " + Dtm_file+"\n"
    txt = txt+"     Résolution (m) :        "+str(Csize)+" m\n"
    txt = txt+"   - Points de passage :     " + Waypoints_file+"\n"
    txt = txt+"   - Foncier :               " + Property_file+"\n"
    txt = txt+"   - Dossier Obstacles :     " + Obs_Dir+"\n\n\n"
    
    txt = txt + "PARAMETRES UTILISES POUR LA MODELISATION:\n\n"
    txt = txt+"   - Pente en long min. :                                                        "+str(min_slope)+" %\n"
    txt = txt+"   - Pente en long max. :                                                        "+str(max_slope)+" %\n"
    txt = txt+"   - Pente en travers max. en tout point :                                       "+str(trans_slope_all)+" %\n"
    txt = txt+"   - Pente en travers max. pour implanter un virage en lacet :                   "+str(trans_slope_hairpin)+"  %\n"
    txt = txt+"   - Pénalité de changement de direction :                                       "+str(penalty_xy)+" m/"+str(angle_hairpin)+"°\n"
    txt = txt+"   - Pénalité de changement du sens de pente en long :                           "+str(penalty_z)+" m\n"
    txt = txt+"   - Rayon de recherche autour d'un pixel :                                      "+str(D_neighborhood)+" m\n"
    txt = txt+"   - Différence max. entre altitude du terrain et altitude théorique du trace :  "+str(max_diff_z)+" m\n"
    txt = txt+"   - Angle au-delà duquel un virage est considéré comme lacet :                  "+str(angle_hairpin)+" °\n"
    txt = txt+"   - Rayon de braquage appliqué aux lacets :                                     "+str(Radius)+" m\n"
    txt = txt+"   - Longueur cumulée max. avec Pente en travers > Pente en travers max. :       "+str(Lmax_ab_sl)+" m\n"
    return txt


def create_param_file(Rspace,param,res_process,str_duree,str_fin,str_debut):
    filename = Rspace +"Parametre_simulation.txt"    
    txt = "SylvaRoaD\n\n"
    txt = txt+"Version du programme: 2.2 08/2021\n"
    txt = txt+"Auteur: Sylvain DUPIRE - SylvaLab\n\n"
    txt = txt+"Date et heure de lancement du script:                                      "+str_debut+"\n"
    txt = txt+"Date et heure a la fin de l'éxécution du script:                           "+str_fin+"\n"
    txt = txt+"Temps total d'éxécution du script:                                         "+str_duree+"\n\n"
    txt = txt+param
    txt = txt+res_process    
    fichier = open(filename, "w")
    fichier.write(txt)
    fichier.close()


def get_points_from_waypoints(Waypoints_file,Dtm_file):
    #Open Dtm_file
    src_ds=gdal.Open(Dtm_file) 
    gt=src_ds.GetGeoTransform()
    
    # Get waypoint
    source_ds = ogr.Open(Waypoints_file)
    source_layer = source_ds.GetLayer()
    geoLocations = []    
    for feat in source_layer:
        geom = feat.GetGeometryRef() 
        idtron = feat.GetField("ID_TRON")
        idpt = feat.GetField("ID_POINT")
        buff = feat.GetField("BUFF_POINT") 
        seg = []  
        mx,my,z = geom.GetPoint(0)
        #Convert from map to pixel coordinates.
        #Only works for geotransforms with no rotation.
        px = int((mx - gt[0]) / gt[1]) #x pixel
        py = int((my - gt[3]) / gt[5]) #y pixel       
        seg.append(idtron)
        seg.append(idpt)
        seg.append(buff)
        seg.append(py)
        seg.append(px)        
        geoLocations.append(seg)
    
    pt_list = np.int16(geoLocations)
    ind = np.lexsort((pt_list[:,1], pt_list[:,0]))    
    return pt_list[ind]
    

def get_waypoints(id_tron,pt_list): 
    seg_list = []
    ptlist2 = pt_list[pt_list[:,0]==id_tron]
    nbpt = ptlist2.shape[0]
             
    for i in range(nbpt-1):
        start = ptlist2[i,3],ptlist2[i,4]   
        end = ptlist2[i+1,3],ptlist2[i+1,4]   
        seg_list.append([start,end,ptlist2[i+1,2]])
    return seg_list
    

def save_param_file(Wspace,Dtm_file,Obs_Dir,Waypoints_file,Property_file,
                    Result_Dir,trans_slope_all,trans_slope_hairpin,
                    min_slope,max_slope,penalty_xy,penalty_z,
                    D_neighborhood,max_diff_z,angle_hairpin,Lmax_ab_sl,
                    Rspace,Radius):
    param = []
    param.append([Wspace,Dtm_file,Obs_Dir,Waypoints_file,Property_file,
                    Result_Dir,trans_slope_all,trans_slope_hairpin,
                    min_slope,max_slope,penalty_xy,penalty_z,
                    D_neighborhood,max_diff_z,angle_hairpin,Lmax_ab_sl,Radius])
    param = np.array(param)
    np.save(Rspace+"SylvaRoaD_param.npy",param)


def ArrayToGtiff(Array,file_name,Extent,nrows,ncols,Csize,road_network_proj,nodata_value,raster_type='INT32'):
    """
    Create Tiff raster from numpy array   
    ----------
    Parameters
    ----------
    Array:             np.array    Array name
    file_name:         string      Complete name of the output raster
    Extent:            list        Extent of the area : [xmin,xmax,ymin,ymax]
    nrows:             int         Number of rows in the array
    ncols:             int         Number of columns in the array
    Csize:             int, float  Cell resolution of the array  
    road_network_proj: string      Spatial projection
    nodata_value:      int, float  Value representing nodata in the array
    raster_type:       string      'INT32' (default),'UINT8','UINT16','FLOAT32','FLOAT16'

    """
    xmin,xmax,ymin,ymax=Extent[0],Extent[1],Extent[2],Extent[3]
    xres=(xmax-xmin)/float(ncols)
    yres=(ymax-ymin)/float(nrows)
    geotransform=(xmin,xres,0,ymax,0, -yres)
    if raster_type=='INT32':
        #-2147483648 to 2147483647
        DataType = gdal.GDT_Int32    
    elif raster_type=='UINT8':
        #0 to 255
        DataType = gdal.GDT_Byte
    elif raster_type=='UINT16':
        #0 to 65535    
        DataType = gdal.GDT_UInt16
    elif raster_type=='INT16':
        #-32768 to 32767 
        DataType = gdal.GDT_Int16
    elif raster_type=='FLOAT32':
        #Single precision float: sign bit, 8 bits exponent, 23 bits mantissa
        DataType = gdal.GDT_Float32
    elif raster_type=='FLOAT16':
        #Half precision float: sign bit, 5 bits exponent, 10 bits mantissa
        DataType = gdal.GDT_Float16
    target_ds = gdal.GetDriverByName('GTiff').Create(file_name+'.tif', int(ncols), int(nrows), 1, DataType)
    target_ds.SetGeoTransform(geotransform)
    target_ds.SetProjection(road_network_proj)
    target_ds.GetRasterBand(1).WriteArray( Array )
    target_ds.GetRasterBand(1).SetNoDataValue(nodata_value)
    target_ds.GetRasterBand(1).GetStatistics(0,1)
    target_ds.FlushCache()


def test_point_within(segments,dtm,Obs,id_tron,res_process):    
    nrows,ncols = Obs.shape
    #Check final point
    txt=""
    txt_deb = '\n    Tronçon n°'+str(int(id_tron))+" : "
    try:
        end = segments[len(segments)-1][1]    
        #Check initial point
        start = segments[0][0]
        if start[0]<0 or start[0]>nrows or start[1]<0 or start[1]>ncols:
            txt2 =  txt_deb + "Le point initial n'est pas dans l'emprise du MNT"
            txt += txt2
            res_process+= txt2
        else:            
            if Obs[start]== 2 :                
                txt2 = txt_deb + "Le point initial n'est pas dans le parcellaire autorisé"
                txt += txt2
                res_process+= txt2       
            elif Obs[start]== 1 :
                if dtm[start]==-9999:
                    txt2 = txt_deb + "Le point initial n'a pas de valeur MNT valide"
                else:
                    txt2 = txt_deb + "Le point initial est sur un obstacle"
                txt += txt2
                res_process+= txt2     
        
        #Check intermediate point
        if len(txt)>0:
            txt_deb = "\n                  "        
        if len(segments)>1:    
            for i in range(1,len(segments)):
                txt_pt = "Le point de passage ID_POINT "+str(i+1)
                start = segments[i][0]
                if start[0]<0 or start[0]>nrows or start[1]<0 or start[1]>ncols:
                    txt2 = txt_deb + txt_pt + " n'est pas dans l'emprise du MNT"
                    txt += txt2
                    res_process+= txt2
                else:
                    if Obs[start]== 2 :                
                        txt2 = txt_deb + txt_pt+ " n'est pas dans le parcellaire autorisé"
                        txt += txt2
                        res_process+= txt2       
                    elif Obs[start]== 1 :
                        if dtm[start]==-9999:
                            txt2 = txt_deb +txt_pt+ " n'a pas de valeur MNT valide"
                        else:
                            txt2 = txt_deb +txt_pt+ " est sur un obstacle"
                        txt += txt2
                        res_process+= txt2   
        
        #check final point
        if len(txt)>0:
            txt_deb = "\n                  "
        if end[0]<0 or end[0]>nrows or end[1]<0 or end[1]>ncols:
            txt2 =  txt_deb + "Le point final n'est pas dans l'emprise du MNT"
            txt += txt2
            res_process+= txt2
        else:           
            if Obs[end]== 2 :                
                txt2 = txt_deb + "Le point final n'est pas dans le parcellaire autorisé"
                txt += txt2
                res_process+= txt2       
            elif Obs[end]== 1 :
                if dtm[end]==-9999:
                    txt2 = txt_deb + "Le point final n'a pas de valeur MNT valide"
                else:
                    txt2 = txt_deb + "Le point final est sur un obstacle"
                txt += txt2
                res_process+= txt2     
        
    except:
        txt = '\n    Tronçon n°'+str(int(id_tron))+" : Il faut au minimum deux points pour réaliser l'analyse"
        res_process+= txt
        end=""
            
    if len(txt)>0: 
        test=0
        print(txt)
        res_process += '\n'
    else:
        test=1
    return test, res_process,end
      
    


def road_finder_exec_force_wp(Dtm_file,Obs_Dir,Waypoints_file,Property_file,
                              Result_Dir,trans_slope_all,trans_slope_hairpin,
                              min_slope,max_slope,penalty_xy,penalty_z,
                              D_neighborhood,max_diff_z,angle_hairpin,
                              Lmax_ab_sl,Wspace,Radius):
    
    print("\nSylvaRoaD - v2.2")
    Hdebut = datetime.datetime.now()
    print("\n  Verification des donnees spatiales")
    #Test if spatial data are OK
    test,mess,Csize = check_files(Dtm_file,Waypoints_file,Property_file)
    
    #Save parameters into npy file
    param = get_param(trans_slope_all,trans_slope_hairpin,
              min_slope,max_slope,
              penalty_xy,penalty_z,
              D_neighborhood,max_diff_z,angle_hairpin,
              Dtm_file,Obs_Dir,Waypoints_file,Property_file,Csize,Lmax_ab_sl,Radius)
    
    Rspace =create_res_dir(Result_Dir,
                           trans_slope_all,trans_slope_hairpin,
                           min_slope,max_slope,
                           penalty_xy,penalty_z,
                           D_neighborhood)
    
    save_param_file(Wspace,Dtm_file,Obs_Dir,Waypoints_file,Property_file,
                    Result_Dir,trans_slope_all,trans_slope_hairpin,
                    min_slope,max_slope,penalty_xy,penalty_z,
                    D_neighborhood,max_diff_z,angle_hairpin,Lmax_ab_sl,
                    Rspace,Radius)
    
    if not test:
        print(mess)
        
    else:    
        print("\n  Chargement des donnees")
        #load data   
        dtm,Extent,Csize,proj = load_float_raster(Dtm_file)
        nrows,ncols=dtm.shape
        if Obs_Dir!='':
            Obs = prepa_obstacle(Obs_Dir,Extent,Csize,ncols,nrows)
        else:
            Obs = np.zeros_like(dtm,dtype=np.int8)
        
        pt_list=get_points_from_waypoints(Waypoints_file,Dtm_file)  
        tron_list = np.unique(pt_list[:,0])
        
        if Property_file!="":
            Fonc = shapefile_to_np_array(Property_file,Extent,Csize,"FONC_OK",
                                     order_field=None,order=None)
        else:
            Fonc = np.ones_like(dtm,dtype=np.int8)
        
        #get usefull variables
        print("  Initialisation du traitement")
           
        road_network_proj,proj = get_proj_from_road_network(Waypoints_file)  
        trans_slope_all *= 1.
        trans_slope_hairpin *= 1.
        min_slope *= 1. 
        max_slope *= 1. 
        penalty_xy *= 1.
        #penalty_xy = Radius*(2*math.pi+1)   
        #penalty_xy =0
        penalty_z *= 1. 
        D_neighborhood *= 1. 
        max_diff_z *= 1.
        Obs[dtm==-9999]=1
        Obs[Fonc==0]=2
        del Fonc
        gc.collect()
        
        #Compute Slope raster and Local Slope raster
        Perc_Slope = get_Slope(Dtm_file)
        Perc_Slope[dtm==-9999]=-9999
        Local_Slope = cy.calc_local_slope(Perc_Slope,1.25*Radius,Csize,
                                          trans_slope_hairpin)                            
          
        #Build neigborhood table
        IdVois, Id, Tab_corresp,IdPix,Slope,Dist,Az = build_NeibTable(D_neighborhood,Csize,dtm,np.int8(Obs>0),min_slope,max_slope)
        
        res_process = '\n\nRésultat par tronçon'
        
        Generaltest=0
        
        for id_tron in tron_list:  
            print("\n  Traitement du tronçon n°"+str(id_tron))
            segments = get_waypoints(id_tron,pt_list)           
            #Check if points are within MNT/property and are not ostacles
            test, res_process,end = test_point_within(segments,dtm,Obs,id_tron,res_process)
            if not test : continue
                
            #Check if points are within possible prospection
            Dist_to_End = cy.calcul_distance_de_cout(end[0],end[1],np.int8(Obs==0),Csize,Max_distance=100000)    
            test=1
            for i in range(0,len(segments)):
                start = segments[i][0]
                if Dist_to_End[start]<0:                    
                    if i==0:
                        txt = '\n    Tronçon n°'+str(int(id_tron))+' : Des obstacles empêchent de joindre le début et la fin du tronçon'
                    else:
                        txt = '\n    Tronçon n°'+str(int(id_tron))+" : Des obstacles empêchent d'atteindre le point de passage ID_POINT "+str(i+1)
                    print(txt)
                    res_process+= txt+'\n'
                    test=0
            
            if not test:continue
            
            #Process
            newObs = np.copy(np.int8(Obs>0))
            newObs[Dist_to_End<0]=1
                     
            
            Path,test = Astar_buf_wp(segments,Slope,IdVois, Id, Tab_corresp,IdPix,Az,Dist,
                                    min_slope,max_slope,penalty_xy,penalty_z,Dist_to_End,
                                    Local_Slope,Perc_Slope,Csize,dtm,max_diff_z,
                                    trans_slope_all,newObs,angle_hairpin,Lmax_ab_sl,Radius,
                                    D_neighborhood)
            
            Lsl=np.sum(Path[:,6]) 
            nb_lac = len(get_id_lacets(Path,angle_hairpin))  
            if test==1:                             
                Path_to_lineshape(Path,Rspace+'Troncon_'+str(int(id_tron))+'_complet.shp',proj,Extent,Csize,dtm,nb_lac)   
                if nb_lac>0:
                    NewPath = trace_lace(Path, Radius,Extent,Csize,angle_hairpin,dtm,coefplat=2)
                    NewPath_to_lineshape(NewPath,Rspace+'Troncon_'+str(int(id_tron))+'_lacets_corriges.shp',proj)                     
                    if  Generaltest==0:
                        ArrayToGtiff(Local_Slope,Rspace+"PenteLocale_Lacet",Extent,nrows,ncols,
                                 Csize,road_network_proj,255,raster_type='UINT8') 
                        Generaltest=1
                    #Path_to_lace(Path,Rspace+'Lacets_Troncon_'+str(int(id_tron))+'.shp',proj,Extent,Csize,dtm)
                txt = '\n    Tronçon n°'+str(int(id_tron))+' : Un chemin optimal a été trouvé. '
                txt +='\n                  Longueur planimétrique : '+str(int((Path[-1,4])+0.5))+" m"
                if nb_lac>0:
                    txt +='\n                  Longueur planimétrique (avec lacets corrigés) : '
                    txt +=str(int(np.sum(NewPath[:,4])+0.5))+" m"
                txt +='\n                  Nombre de lacets : '+str(int(nb_lac))
                if Lsl>0:
                    txt += "\n                  Sur "+str(int(Lsl+0.5))+" m, la pente en travers est supérieure à la pente en travers max."
                print(txt) 
                
            else: 
                Path_to_lineshape(Path,Rspace+'Troncon_'+str(int(id_tron))+'_incomplet.shp',proj,Extent,Csize,dtm,nb_lac)
                txt = '\n    Tronçon n°'+str(int(id_tron))+' : Aucun chemin trouvé. '
                txt = '\n                  Le chemin le plus proche du but a été sauvegardé. '               
                print(txt) 
            res_process+= txt+"\n"

        str_duree,str_fin,str_debut=heures(Hdebut,'FR')        
        create_param_file(Rspace,param,res_process,str_duree,str_fin,str_debut)
        print("\n  Tous les tronçons ont été traités")