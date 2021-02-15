from flask import Flask, request, jsonify, render_template, make_response
from flask_restx import Api, Resource, fields
from datetime import timedelta
import subprocess
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds
import pandas as pd
from minio import Minio
import os

from data_processing.api.radiologyPreprocessingLibrary.app.service import dicom_to_binary

# Setup configurations
VERSION      = "branch:"+subprocess.check_output(["git","rev-parse" ,"--abbrev-ref", "HEAD"]).decode('ascii').strip()

# Setup App and Api
app = Flask(__name__)
app.config.from_pyfile('app.cfg', silent=False)

api = Api(app, version=VERSION,
          title='radiologyPreprocessingLibrary',
          description='Preprocessing utility functions for radiology data',
          ordered=True)

object_client = Minio(app.config.get('OBJECT_URI'),
                      access_key=app.config.get('OBJECT_USER'),
                      secret_key=app.config.get('OBJECT_PASSWORD'), secure=False)
# param models
image_params = api.model("DicomToImage",
    {
        "paths": fields.String(description="List of dicom paths", required=True, example=['/path/to/1.dcm','/path/to/2.dcm']),
        "width": fields.String(description="Output image width", required=True, example=512),
        "height": fields.String(description="Output image height", required=True, example=512)
    }
)
path_params = api.model("DownloadImage",
    {
        "output_location": fields.String(description="Local path to download file", required=True, example="/path/to/output.parquet")
    }
)

# FUTURE: a subsetting function that selects instance # list before this?
@api.route('/radiology/images/<project_id>/<scan_id>',
           methods=['GET', 'POST', 'DELETE'],
           doc={"description": "CRUD dicoms in given scan to Image files."}
)
class DicomToImage(Resource):

    @api.doc(
        params={'project_id': 'Project Id',
                'scan_id': 'Scan Identifier'},
        responses={200: "Success",
                   400: "Images not found"}
    )
    @api.expect(path_params)
    def get(self, project_id, scan_id):
        # TODO could be a generic function
        output_path = request.json["output_location"]
        print(project_id)
        print(scan_id)
        print(output_path)

        try:
            object_name = "radiology-images/" + scan_id + ".parquet"
            response = object_client.fget_object(project_id, object_name, output_path)
            print(dict(response.metadata))
            # populate response
            metadata = response.metadata
            metadata['message'] = f"Downloaded object {project_id}/{object_name} at {output_path}"

            # alternatively, get downloadable url with object_client.get_presigned_url() -> request.get(url)
            # this doesn't work well with binary field..
            return make_response(jsonify(dict(response.metadata)), 200)

        except Exception as ex:
            response = {'payload': ex}
            return make_response(jsonify(response), 400)


    @api.doc(
        params={'project_id': 'Project Id',
                'scan_id': 'Scan Identifier'},
        responses={200: "Success",
                   400: "Images already exist"}
    )
    @api.expect(image_params)
    def post(self, project_id, scan_id):

        # get request params
        paths = request.json["paths"]
        width = request.json["width"]
        height = request.json["height"]

        print(paths)
        print(width)
        print(height)
        print(project_id)
        print(scan_id)

        binaries = []
        for path in paths:
            binaries.append(dicom_to_binary(path, int(width), int(height)))

        print(len(binaries))

        # save in parquet
        if not object_client.bucket_exists(project_id):
            object_client.make_bucket(project_id)

        uri = os.path.join(project_id, "radiology-images", scan_id + ".parquet")
        # some minimal parquet schema. save request.json also!
        df = pd.DataFrame({"content": binaries})

        # add post request params
        for key, val in request.json.items():
            df[key] = val

        minio = pa.fs.S3FileSystem(scheme="http",
                                   endpoint_override=app.config.get("OBJECT_URI"),
                                   access_key=app.config.get("OBJECT_USER"),
                                   secret_key=app.config.get("OBJECT_PASSWORD"))

        table = pa.Table.from_pandas(df, preserve_index=False)

        # alternatively, write_to_dataset can write partitioned parquets, along with write_metadata
        pq.write_table(table, uri, filesystem=minio)
        response = {'message': f"Parquet created at {uri}"}
        return make_response(jsonify(response), 200)


    @api.doc(
        params={'project_id': 'Project Id',
                'scan_id': 'Scan Identifier'},
        responses={200: "Success",
                   400: "Images not found"}
    )
    def delete(self, project_id, scan_id):
        # TODO could be a generic function
        print(project_id)
        print(scan_id)

        try:
            object_name = "radiology-images/" + scan_id + ".parquet"
            object_client.remove_object(project_id, object_name)

            response = {'message': f"Removed object {project_id}/{object_name}"}

            return make_response(jsonify(dict(response)), 200)

        except Exception as ex:
            response = {'payload': ex}
            return make_response(jsonify(response), 400)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, threaded=True, debug=False)
