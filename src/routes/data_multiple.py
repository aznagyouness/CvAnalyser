


from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController
from models.AssetModel import AssetModel
from models.db_schemes import Asset
from models.enums.AssetTypeEnum import AssetTypeEnum
from models.ProjectModel import ProjectModel
from models.db_schemes import Project
from models.enums.DataBaseEnum import DataBaseEnum

import aiofiles
from models import ResponseSignal
import logging
from typing import List

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload_all/{project_id}")
async def upload_data(request: Request, project_id: str, files: List[UploadFile],
                      app_settings: Settings = Depends(get_settings)):
    
    # instatiate the ProjectModel(db_client, project_colection, app_settings)
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)

    # here pydantic verfiy the project_id is alphanumeric
    project = await project_model.get_or_insert_one_project_document(project_id=project_id)

    # instantiate the AssetModel(db_client, asset_colection, app_settings)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)



    # validate the file properties
    data_controller = DataController()

    # get the project directory path
    project_controller = ProjectController()
    project_dir_path = project_controller.get_project_path(project_id=project_id)

    
    results = []
    inserted_assets = []
    non_inserted_assets = []
    
    for file in files:
        # validate the file properties
        is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

        if not is_valid:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": result_signal,
                "file_id": None
            })
            continue

        file_path, file_id = data_controller.generate_unique_filepath(
            orig_file_name=file.filename,
            project_id=project_id
        )

        try:
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                    await f.write(chunk)
            
            results.append({
                "filename": file.filename,
                "success": True,
                "file_id": file_id
            })
            
        except Exception as e:
            logger.error(f"Error while uploading file {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": ResponseSignal.FILE_UPLOAD_FAILED.value,
                "file_id": None
            })
        
        # store the file metadata in the database
        # asset mean 1 file metadata
        
        asset_resource = Asset(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value,
            asset_name=file_id,
            asset_size=os.path.getsize(file_path)
        )

        asset_record = await asset_model.insert_asset_document(asset=asset_resource)

        if asset_record:
            inserted_assets.append(str(asset_record.id))

        
        

    # Calculate counts
    uploaded_files = sum(1 for result in results if result['success'])
    non_uploaded_files = len(results) - uploaded_files

    inserted_files_db = len(inserted_assets)
    non_inserted_files_db = len(results) -inserted_files_db

    # Check if all files failed
    if all(not result['success'] for result in results):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value,
                "uploaded_files": uploaded_files,
                "non_uploaded_files": non_uploaded_files,
                "inserted_files_db": inserted_files_db,
                "non_inserted_files_db": non_inserted_files_db,
                "details": results,

            }
        )
    
    # Check if some files failed
    if any(not result['success'] for result in results):
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                "uploaded_files": uploaded_files,
                "non_uploaded_files": non_uploaded_files,
                "inserted_files_db": inserted_files_db,
                "non_inserted_files_db": non_inserted_files_db,
                "details": results
            }
        )
    
    # All files succeeded
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            "uploaded_files": uploaded_files,
            "non_uploaded_files": non_uploaded_files,
            "details": results,
            "inserted_files_db": inserted_files_db,
            "non_inserted_files_db": non_inserted_files_db,
        }
    )


