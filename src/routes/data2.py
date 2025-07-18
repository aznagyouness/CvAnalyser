from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from helpers import get_settings
from helpers.config import Settings
import logging
from pathlib import Path
from typing import List

base_router = APIRouter()
logger = logging.getLogger(__name__)

@base_router.post("/upload")
async def upload_files(
    app_settings: Settings = Depends(get_settings),
    files: List[UploadFile] = File(..., description="Files to upload")
):
    """
    Upload multiple files with size and extension validation
    
    - Validates at least one file exists
    - Processes files sequentially
    - Validates each file's extension
    - Streams files in chunks to measure size
    - Enforces maximum file size limit per file
    - Secures against path traversal in filenames
    - Comprehensive error handling
    - Guaranteed resource cleanup
    - Returns individual results for each file
    """
    # Validate at least one file exists
    if files is None or len(files)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "No files provided"})
        

    
    results = []
    CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
    max_size = app_settings.FILE_MAX_SIZE
    if files :
        for file in files:
            try:
                # Secure filename processing
                filename = Path(file.filename).name
                extension = filename.split(".")[-1].lower() if "." in filename else ""
                
                # Validate file extension
                if not extension or extension not in app_settings.FILE_ALLOWED_EXTENSIONS:
                    allowed = ", ".join(app_settings.FILE_ALLOWED_EXTENSIONS)
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid file type '{extension}' for {filename}. Allowed types: {allowed}"
                    )

                # Process file content in chunks
                size = 0
                while chunk := await file.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_size:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File '{filename}' exceeds size limit of {max_size} bytes"
                        )

                # Add successful upload result
                results.append({
                    "filename": filename,
                    "size_in_bytes": size,
                    "size_in_mb": round(size / (1024 * 1024), 2),
                    "extension": extension,
                    "status": "success"
                })

            except HTTPException as e:
                # Capture individual file errors while continuing processing
                results.append({
                    "filename": filename,
                    "error": e.detail,
                    "status": "failed"
                })
            except Exception as e:
                # Log unexpected errors
                logger.error(f"File '{filename}' processing failed: {str(e)}", exc_info=True)
                results.append({
                    "filename": filename,
                    "error": "Internal server error during processing",
                    "status": "failed"
                })
            finally:
                # Ensure file resources are always released
                await file.close()

        # Check if all files failed
        if all(result['status'] == 'failed' for result in results):
            raise HTTPException(
                status_code=400,
                detail="All files failed to upload. See individual errors in response"
            )

        return {"results": results, "number_of_files": len(files), "status": "completed", 
                "number_of_successful_uploads": len([r for r in results if r['status'] == 'success']),
                "number_of_failed_uploads": len([r for r in results if r['status'] == 'failed'])}


"""
Key Enhancements for Multi-File Support:

1. Multi-File Parameter:
   - Accepts multiple files using:
     files: List[UploadFile] = File(..., description="Files to upload")

2. Individual File Processing:
   - Each file is processed sequentially in a loop
   - Resources are properly closed using a `finally` block
   - Maintains efficient chunked reading (1MB) for low memory usage

3. Comprehensive Result Reporting:
   - Returns detailed upload result for each file, including:
     • Filename
     • File size in bytes
     • File size in MB (rounded to 2 decimals)
     • File extension
     • Upload status (success/failed)
     • Error message (if upload failed)

4. Improved Error Handling:
   - Continues processing remaining files even after encountering errors
   - Captures individual file errors and includes them in the response
   - Special handling when **all** files fail: raises HTTPException
   - Error messages include the filename for context
   - Prevents path traversal attacks with secure filename handling

5. Efficient Resource Management:
   - Files are closed immediately after processing
   - Maintains low memory footprint via chunked streaming
   - Early termination of processing when file exceeds size limit

6. Response Structure:
   Example JSON format:
   {
     "results": [
       {
         "filename": "document.pdf",
         "size_in_bytes": 1048576,
         "size_in_mb": 1.0,
         "extension": "pdf",
         "status": "success"
       },
       {
         "filename": "image.jpg",
         "error": "File size exceeds limit",
         "status": "failed"
       }
     ]
   }

7. Validation Enhancements:
   - Ensures the file list is not empty
   - Validates file extensions with context (filename included)
   - Validates size per file with specific error messages

8. Error Recovery:
   - Endpoint processes all files, even if some fail
   - Only raises HTTPException when **no files** succeed
   - Returns a detailed summary of successes and failures

This implementation maintains the original single-file security and efficiency while introducing robust multi-file upload support.

It provides:
- Detailed per-file results
- Atomic (independent) processing of each file
- Guaranteed resource cleanup
- Clear and contextual error messages
- Optimized memory usage
- Clean and structured API response

The endpoint now supports multiple file uploads in a single request while ensuring security, clarity, and performance in production environments.
"""
