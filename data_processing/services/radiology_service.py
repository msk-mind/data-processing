'''
Created: February 2021
@author: aukermaa@mskcc.org

Given a scan (container) ID
1. resolve the path to the dicom folder
2. for all dicoms, rescale into HU and optionally window
3. store results on HDFS and add metadata to the graph

'''
# General imports
import os, sys, subprocess, uuid, requests, socket
import click
from concurrent.futures import ProcessPoolExecutor

# Server imports
from flask import Flask, request, jsonify, render_template, make_response
from flask_restx import Api, Resource, fields

# From common
from data_processing.common.config          import ConfigSet
from data_processing.common.custom_logger   import init_logger
from data_processing.common.Neo4jConnection import Neo4jConnection

from data_processing.scanManager.windowDicoms       import window_dicom_with_container
from data_processing.scanManager.extractRadiomics   import extract_radiomics_with_container
from data_processing.scanManager.extractVoxels      import extract_voxels_with_container
from data_processing.scanManager.generateScan       import generate_scan_with_container
from data_processing.scanManager.collectCSV         import collect_csv_with_container

logger = init_logger("radiology-service.log")
    
cfg = ConfigSet("APP_CFG",  config_file="config.yaml")
VERSION      = "branch:"+subprocess.check_output(["git","rev-parse" ,"--abbrev-ref", "HEAD"]).decode('ascii').strip()
HOSTNAME     = socket.gethostname()
PORT         = int(cfg.get_value("APP_CFG::radiology_service_port"))
NUM_PROCS    = int(cfg.get_value("APP_CFG::radiology_service_processes"))

app = Flask(__name__)
api = Api(app, version=VERSION, title='MIND Radiology Processing Service', description='Job-style endpoints for radiology image processing', ordered=True)
executor = ProcessPoolExecutor(NUM_PROCS) 
conn   = Neo4jConnection(uri=cfg.get_value("APP_CFG::GRAPH_URI"), user=cfg.get_value("APP_CFG::GRAPH_USER"), pwd=cfg.get_value("APP_CFG::GRAPH_PASSWORD"))

# general models
general_model = api.model("Query+Job Model", 
    {
        "query":  fields.String(description="Tag/name of output record", required=True, example='my_radiomics'),
        "params": fields.Raw(description="Job parameters", required=True)
    }
)

# param models
extract_voxels_model = api.model("Resample and Extract Voxels", 
    {
        "job_tag": fields.String(description="Tag/name of output record", required=True, example='my_voxels'),
        "image_input_tag": fields.String(description="Tag/name of input image record", required=True, example='generated_mhd'),
        "label_input_tag": fields.String(description="Tag/name of label image record", required=True, example='user_segmentations'),
        "resampledPixelSpacing": fields.List(fields.Float, description="Pixel resampling in mm in x,y,z", required=True, example=[1,1,1]),
    }
)

# param models
extract_radiomics_model = api.model("Extract Radiomics", 
    {
        "job_tag": fields.String(description="Tag/name of output record", required=True, example='my_radiomics'),
        "image_input_tag": fields.String(description="Tag/name of input image record", required=True, example='generated_mhd'),
        "label_input_tag": fields.String(description="Tag/name of label image record", required=True, example='user_segmentations'),
        "enableAllImageTypes": fields.Boolean(description="Toggle all images", required=False, example=False),
        "strictGeometry": fields.Boolean(description="Ensure dimensions and voxel spacing of input image match input mask", required=False, example=True),
        "RadiomicsFeatureExtractor": fields.Raw(description="Key-value pairs for radiomics feature extractor", required=False, example={"interpolator": 'sitkBSpline'}),
    }
)

# param models
window_dicom_model = api.model("Scale and Window CT Dicom Datasets",
    {
        "job_tag": fields.String(description="Tag/name of output record", required=True, example='my_windowed_dicoms'),
        "dicom_input_tag": fields.String(description="Tag/name of input image record", required=True, example='dicoms'),
        "window": fields.Boolean(description="Toggle window function", required=False, example=True),
        "window_low_level":  fields.Float(description="Low window value", required=False,  example=-100),
        "window_high_level": fields.Float(description="High window value", required=False, example=100),
    }
)

# param models
generate_scan_model = api.model("Generate Volumetric Image",
    {
        "job_tag": fields.String(description="Tag/name of output record", required=True, example='my_nrrd'),
        "dicom_input_tag": fields.String(description="Tag/name of input image record", required=True, example='dicoms'),
        "itkImageType": fields.String(description="A valid ITK image file extention", required=True, example='nrrd'),
    }
)

# param models
collect_parquet_model = api.model("Collect CSVs",
    {
        "output_container": fields.String(description="Parquet container qualified address", required=True, example='my_parquet_store'),
        "input_tags": fields.List(fields.String, description="Input tags to add to container slice", required=True, example=["csv-job-1", "csv-job-2"])
    }
)


@api.route('/mind/api/v1/<function>/<cohort_id>/submit', methods=['POST'])
class runMethods(Resource):
    @api.expect(general_model, validate=True)
    def post(self, function, cohort_id):
        """ Execution function for container IDs matching a graph query """
        data = request.json
        query  = data.get("query")
        params = data.get("params")

        container_ids = [rec.data() for rec in conn.query(query)]

        # Check for cohort existence
        if not len(container_ids) >= 1: 
            return make_response("No matching containers found!", 400)
         # Check for cohort existence
        if not len(container_ids[0].keys()) == 1: 
            return make_response("Too many return keys, please only return (node).qualified_address", 400)   
        if not "qualified_address" in list(container_ids[0].keys())[0]: 
            return make_response("Cannot find qualified address, please return (node).qualified_address", 400)  

        container_ids = [list(rec.values())[0] for rec in container_ids]
        print (container_ids)

        for container_id in container_ids: requests.post(f"http://{HOSTNAME}:{PORT}/mind/api/v1/{function}/{cohort_id}/{container_id}/submit", json=params)



@api.route('/mind/api/v1/window_dicom/<cohort_id>/<container_id>/submit', methods=['POST'])
class API_window_dicom(Resource):
    @api.expect(window_dicom_model, validate=True)
    def post(self, cohort_id, container_id):
        """Submit a scale and window CT dicom job"""
        job_id = str(uuid.uuid4())
        future = executor.submit (window_dicom_with_container, cohort_id, container_id, request.json)
        return make_response( {"message": f"Submitted job {job_id} with future {future}", "job_id": job_id }, 202 )

@api.route('/mind/api/v1/extract_voxels/<cohort_id>/<container_id>/submit', methods=['POST'])
class API_extract_voxels(Resource):
    @api.expect(extract_voxels_model, validate=True)
    def post(self, cohort_id, container_id):
        """Submit an volumentric resample and voxel extraction job"""
        job_id = str(uuid.uuid4())
        future = executor.submit (extract_voxels_with_container, cohort_id, container_id, request.json)
        return make_response( {"message": f"Submitted job {job_id} with future {future}", "job_id": job_id }, 202 )

@api.route('/mind/api/v1/extract_radiomics/<cohort_id>/<container_id>/submit', methods=['POST'])
class API_extract_radiomics(Resource):
    @api.expect(extract_radiomics_model, validate=True)
    def post(self, cohort_id, container_id):
        """Submit an extract radiomics job"""
        job_id = str(uuid.uuid4())
        future = executor.submit (extract_radiomics_with_container, cohort_id, container_id, request.json)
        return make_response( {"message": f"Submitted job {job_id} with future {future}", "job_id": job_id }, 202 )

@api.route('/mind/api/v1/generate_scan/<cohort_id>/<container_id>/submit', methods=['POST'])
class API_generate_scan(Resource):
    @api.expect(generate_scan_model, validate=True)
    def post(self, cohort_id, container_id):
        """Submit a generate scan job"""
        job_id = str(uuid.uuid4())
        future = executor.submit (generate_scan_with_container, cohort_id, container_id, request.json)
        return make_response( {"message": f"Submitted job {job_id} with future {future}", "job_id": job_id }, 202 )

@api.route('/mind/api/v1/collect_parquet/<cohort_id>/<container_id>/submit', methods=['POST'])
class API_collect_parquet(Resource):
    @api.expect(collect_parquet_model, validate=True)
    def post(self, cohort_id, container_id):
        """Submit a parquet collection job"""
        job_id = str(uuid.uuid4())
        future = executor.submit (collect_csv_with_container, cohort_id, container_id, request.json)
        return make_response( {"message": f"Submitted job {job_id} with future {future}", "job_id": job_id }, 202 )

@api.route('/service/health', methods=['GET'])
class API_heatlh(Resource):
    def get(self):
        try:
            executor.submit(print, "Test")
            return make_response("I'm doing okay! :)")
        except:
            return make_response("I'm not okay :(", 400)
        

if __name__ == '__main__':
    # Setup App/Api
    if sys.argv[1] == "start":
        logger.info(f"Running in API mode")
        logger.info(f"Starting worker on {HOSTNAME}:{PORT}")
        app.run(host=HOSTNAME,port=PORT, debug=False)

