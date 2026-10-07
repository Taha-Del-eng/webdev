import os, cloudinary, cloudinary.uploader

def configured():
    return all(os.getenv(k) for k in ("CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET"))

def configure():
    if configured():
        cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"), api_key=os.getenv("CLOUDINARY_API_KEY"), api_secret=os.getenv("CLOUDINARY_API_SECRET"), secure=True)

def upload_file(file_obj, folder="yours-mart/products"):
    configure()
    if not configured():
        raise RuntimeError("Cloudinary is not configured.")
    result = cloudinary.uploader.upload(file_obj, folder=folder, resource_type="image")
    return result["secure_url"]
