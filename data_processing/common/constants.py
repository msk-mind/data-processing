'''
Created on November 16, 2020

@author: rosed2@mskcc.org
'''
import os
# Application Constants

#### Table Names ####
TABLE_DIR			='tables/'
# clinical
DIAGNOSIS_TABLE		=TABLE_DIR + 'diagnosis'
MEDICATION_TABLE	=TABLE_DIR + 'medication'
PATIENT_TABLE		=TABLE_DIR + 'patient'

# radiology
DICOM_TABLE			=TABLE_DIR + 'dicom'
SCAN_TABLE 			=TABLE_DIR + 'scan'
SCAN_ANNOTATION_TABLE		=TABLE_DIR + 'scan_annotation'
FEATURE_TABLE		=TABLE_DIR + 'feature'

#### Raw Data Directories ####
DICOMS				='dicoms'
SCANS				='scans'
SCAN_ANNOTATIONS	='scan_annotations'
PATHOLOGY_ANNOTATIONS	='pathology_annotations'
FEATURES			='features'

# Configurations
APP_CFG				='APP_CFG'
DATA_CFG			='DATA_CFG'
SCHEMA_FILE			='data_ingestion_template_schema.yml'
PUBLIC_DIR          ='/gpfs/mskmind_ess/mind_public'

# Annotation API Data Mappings
PROJECT_MAPPING = {'msk_mind_ov': "OV_16-158", "msk_mind_lung": "LUNG_18-193"}
ANNOTATION_TABLE_MAPPINGS = {"regional":\
 {"DATA_TYPE":"REGIONAL_CONCAT_GEOJSON", "GEOJSON_COLUMN_NAME": "concat_geojson"}, \
 "point": {"DATA_TYPE": "POINT_GEOJSON", "GEOJSON_COLUMN_NAME": "geojson"} \
    }



def PROJECT_LOCATION(cfg):
    """
    ROOT_PATH is a path to mind data e.g. /gpfs/mind/data or hdfs://server:port/data

    :param cfg:
    :return: ROOT_PATH/PROJECT_NAME
    """
    return os.path.join(cfg.get_value(path=DATA_CFG+'::ROOT_PATH'), cfg.get_value(path=DATA_CFG+'::PROJECT'))


def TABLE_LOCATION(cfg, is_source=False):
    return "{0}/tables/{1}".format(PROJECT_LOCATION(cfg), TABLE_NAME(cfg, is_source))

def TABLE_NAME(cfg, is_source=False):

    if is_source:   
        table_name = cfg.get_value(path=DATA_CFG+'::SOURCE_DATA_TYPE').upper()
    else:
        table_name = cfg.get_value(path=DATA_CFG+'::DATA_TYPE').upper()

    dataset_name = cfg.get_value(path=DATA_CFG+'::DATASET_NAME')
    
    if dataset_name != "" and dataset_name is not None:
        table_name += "_{0}".format(dataset_name)

    return table_name
