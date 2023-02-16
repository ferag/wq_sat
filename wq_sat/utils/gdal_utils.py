import re
import os

from osgeo import gdal, osr

def lonlat_to_xy(lon, lat, ds):
    """
    Parameters
    ----------
    lon: str
    lat: str
    ds: GDAL Dataset
    Returns
    -------
    A pair of coordinates in meters/pixels ????
    """

    xoff, a, b, yoff, d, e = ds.GetGeoTransform()
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjection())
    srsLatLon = osr.SpatialReference()
    srsLatLon.SetWellKnownGeogCS("WGS84")
    ct = osr.CoordinateTransformation(srsLatLon, srs)

    (xp, yp, h) = ct.TransformPoint(lon, lat, 0.)
    xp -= xoff
    yp -= yoff
    # matrix inversion
    det_inv = 1. / (a * e - d * b)
    x = (e * xp - b * yp) * det_inv
    y = (-d * xp + a * yp) * det_inv
    
    return int(x), int(y)

def check_gdal_format(file_format):
    """
    Check if a file format can be written with GDAL

    Parameters
    ----------
    file_format : str
    """
    driver = gdal.GetDriverByName(file_format)
    if driver:
        metadata = driver.GetMetadata()
        if gdal.DCAP_CREATE in metadata and metadata[gdal.DCAP_CREATE] == 'YES':
            return True
    else:
        return False


def save_gdal(output_path, bands, descriptions, geotransform, geoprojection, file_format='GTiff'):
    """
    Function to save bands into a gdal format

    Parameters
    ----------
    output_path : str
        Output path of the file
    bands : list of 2D np.arrays
        Bands to save. List of len(C)
    descriptions : list of strs
        Descriptions of the bands. List of len(C)
    geotransform
    geoprojection
    file_format
    """
    
    # Create output path if needed
    path_dir = os.path.dirname(output_path)
    if not os.path.exists(path_dir):
        os.makedirs(path_dir)

    # Check file format
    assert check_gdal_format(file_format), 'File format not supported by GDAL (check https://www.gdal.org/formats_list.html)'

    # Create GDAL dataset
    driver = gdal.GetDriverByName(file_format)
    result_dataset = driver.Create(output_path,
                                   bands.shape[1], bands.shape[0], bands.shape[-1],
                                   gdal.GDT_Float64)
    result_dataset.SetGeoTransform(geotransform)
    result_dataset.SetProjection(geoprojection)

    # Save bands and descriptions
    for i, desc in enumerate(descriptions):
        #print('Saving {}'.format(desc))
        result_dataset.GetRasterBand(i+1).SetDescription(desc)
        result_dataset.GetRasterBand(i+1).WriteArray(bands[:,:,i])