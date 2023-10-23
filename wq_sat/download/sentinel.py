"""
Given two dates and the coordinates, download N Sentinel Collections scenes from ESA Sentinel dataHUB.
The downloaded Sentinel collection scenes are compatible with:

Sentinel-2:
    - S2MSI1C: Top-of-atmosphere reflectances in cartographic geometry
    - S2MSI2A: Bottom-of-atmosphere reflectance in cartographic geometry
    
Sentinel-3:
    - OL_1_EFR___: Full Resolution TOA Reflectance
    - OL_1_ERR___: Reduced Resolution TOA Reflectance
----------------------------------------------------------------------------------------------------------

Author: Daniel García Díaz
Email: garciad@ifca.unican.es
Spanish National Research Council (CSIC); Institute of Physics of Cantabria (IFCA)
Advanced Computing and e-Science
Date: Apr 2023
"""

#imports apis
import datetime
import xmltodict
import requests
import os

# Subfunctions
from wq_sat import config
from wq_sat.utils import sat_utils


class download:

    def __init__(self, inidate, enddate, coordinates, platform, producttype, cloud=100):
        """
        Parameters
        ----------
        inidate : Initial date of the query in format: datetime.strptime "%Y-%m-%dT%H:%M:%SZ"
        enddate : Final date of the query in format: datetime.strptime "%Y-%m-%dT%H:%M:%SZ"
        coordinates : dict. Coordinates that delimit the region to be searched.
            Example: {"W": -2.830, "S": 41.820, "E": -2.690, "N": 41.910}}
        producttype : str
            Dataset type. A list of productypes can be found in https://mapbox.github.io/usgs/reference/catalog/ee.html
        cloud: int
            Cloud cover percentage to narrow your search
        
        Attention please!!
        ------------------
        Registration and login credentials are required to access all system features and download data.
        To register, please create a username and password.
        Once registered, the username and password must be added to the credentials.yaml file.
        Example: sentinel: {password: password, user: username}
        """
        
        # Open the request session
        self.session = requests.Session()
        
        #Search parameters
        self.inidate = inidate.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.enddate = enddate.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.platform = platform
        self.producttype = producttype
        self.cloud = int(cloud)
        self.coord = coordinates

        #work path
        self.output_path = os.path.join(config.data_path(), self.platform, self.producttype)        
        if not os.path.isdir(self.output_path):
            os.makedirs(self.output_path)
        
        #ESA APIs
        self.api_url = 'https://scihub.copernicus.eu/dhus/'
        self.credentials = config.load_credentials()['sentinel']
        
        
    def search(self, omit_corners=True):

        # Post the query to Copernicus
        query = {'footprint': '"Intersects(POLYGON(({0} {1},{2} {1},{2} {3},{0} {3},{0} {1})))"'.format(self.coord['W'],
                                                                                                        self.coord['S'],
                                                                                                        self.coord['E'],
                                                                                                        self.coord['N']),
                 'producttype': self.producttype,
                 'platformname': self.platform,
                 'beginposition': '[{} TO {}]'.format(self.inidate, self.enddate)
                 }

        data = {'format': 'json',
                'start': 0,  # offset
                'rows': 100,
                'limit': 100,
                'orderby': '',
                'q': ' '.join(['{}:{}'.format(k, v) for k, v in query.items()])
                }

        response = self.session.post(self.api_url + 'search?',
                                     data=data,
                                     auth=(self.credentials['user'], self.credentials['password']),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        response.raise_for_status()

        # Parse the response
        json_feed = response.json()['feed']

        if 'entry' in json_feed.keys():
            results = json_feed['entry']
            if isinstance(results, dict):  # if the query returns only one product, products will be a dict not a list
                results = [results]
        else:
            results = []

        # Remove results that are mainly corners
        def keep(r):
            for item in r['str']:
                if item['name'] == 'size':
                    units = item['content'].split(' ')[1]
                    mult = {'KB': 1, 'MB': 1e3, 'GB': 1e6}[units]
                    size = float(item['content'].split(' ')[0]) * mult
                    break
            if size > 0.5e6:  # 500MB
                return True
            else:
                return False
        results[:] = [r for r in results if keep(r)]
        print('Found {} results from {}'.format(json_feed['opensearch:totalResults'], self.platform))
        print('Retrieving {} results \n'.format(len(results)))

        return results
    
    def download(self):
        
        scenes = []
        
        #results of the search
        results = self.search()
        if not isinstance(results, list):
            results = [results]

        downloaded, pending= [], []
        for result in results:
            
            url_xml, url, tile_id = result['link'][1]['href'], result['link'][0]['href'], result['title']
            xml = requests.get(url_xml, stream=True, allow_redirects=True, auth=(self.credentials['user'],
                                                                                 self.credentials['password']))

            data = xmltodict.parse(xml.text)
            available = data['entry']['m:properties']['d:Online']
            
            if available == 'true':
                
                r = requests.get(url, stream=True, allow_redirects=True, auth=(self.credentials['user'],
                                                                               self.credentials['password']))
            
                if r.status_code == 200:
                    
                    downloaded.append(tile_id)
                    if self.platform == 'Sentinel-2':
                        tile_path = os.path.join(self.output_path, '{}.SAFE'.format(tile_id))
                    elif self.platform == 'Sentinel-3':
                        tile_path = os.path.join(self.output_path, '{}.SEN3'.format(tile_id))
                        
                    if os.path.isdir(tile_path):
                        print ('Already downloaded \n')
                        continue
                
                    print('Downloading {} ... \n'.format(tile_id))

                    sat_utils.open_compressed(byte_stream=r.content,
                                              file_format='zip',
                                              output_folder=self.output_path)
                else:
                    pending.append(tile_id)
                    print ('The product is offline')
                    print ('Activating recovery mode ...')
                
            else:
                pending.append(tile_id)
                print ('The product {} is offline'.format(tile_id))
                print ('Activating recovery mode ... \n')
                
        return downloaded, pending