from fastapi import FastAPI, APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController
import aiofiles
import asyncio
from models import ResponseSignal
import logging
from typing import List

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

async def process_single_file(
    file: UploadFile,
    project_id: int,
    data_controller: DataController,
    chunk_size: int,
    semaphore: asyncio.Semaphore
):
    """Process a single file with concurrency control"""
    async with semaphore:
        # Validate file
        is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
        if not is_valid:
            return {
                "filename": file.filename,
                "success": False,
                "error": result_signal,
                "file_id": None
            }

        # Generate file path
        file_path, file_id = data_controller.generate_unique_filepath(
            orig_file_name=file.filename,
            project_id=project_id
        )

        try:
            # Write file with chunked upload
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(chunk_size):
                    await f.write(chunk)
            
            return {
                "filename": file.filename,
                "success": True,
                "file_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Upload failed for {file.filename}: {str(e)}")
            return {
                "filename": file.filename,
                "success": False,
                "error": ResponseSignal.FILE_UPLOAD_FAILED.value,
                "file_id": None
            }

@data_router.post("/upload_all_deepseek/{project_id}")
async def upload_data(project_id: int, files: List[UploadFile],
                      app_settings: Settings = Depends(get_settings)):
    
    data_controller = DataController()
    project_controller = ProjectController()
    
    # Create semaphore to limit concurrent uploads (10-20 is optimal)
    concurrency_limit = min(20, max(10, len(files)))
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    # Process all files concurrently
    tasks = []
    for file in files:
        task = process_single_file(
            file=file,
            project_id=project_id,
            data_controller=data_controller,
            chunk_size=app_settings.FILE_DEFAULT_CHUNK_SIZE,
            semaphore=semaphore
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # Calculate counts
    uploaded_files = sum(1 for result in results if result['success'])
    non_uploaded_files = len(results) - uploaded_files
    
    response_content = {
        "uploaded_files": uploaded_files,
        "non_uploaded_files": non_uploaded_files,
        "details": results
    }

    if uploaded_files == 0:  # All failed
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value,
                **response_content
            }
        )
    elif non_uploaded_files > 0:  # Partial success
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                **response_content
            }
        )
    
    # All succeeded
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            **response_content
        }
    )