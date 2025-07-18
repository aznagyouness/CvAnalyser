from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController
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
async def upload_data(project_id: int, files: List[UploadFile],
                      app_settings: Settings = Depends(get_settings)):
    
    data_controller = DataController()
    project_controller = ProjectController()
    project_dir_path = project_controller.get_project_path(project_id=project_id)
    
    results = []
    
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

    # Calculate counts
    uploaded_files = sum(1 for result in results if result['success'])
    non_uploaded_files = len(results) - uploaded_files

    # Check if all files failed
    if all(not result['success'] for result in results):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value,
                "uploaded_files": uploaded_files,
                "non_uploaded_files": non_uploaded_files,
                "details": results
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
            "details": results
        }
    )