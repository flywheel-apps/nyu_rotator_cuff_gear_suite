import logging
import os
import zipfile

log = logging.getLogger(__name__)


def _create_archive(content_dir, arcname, zipfilepath=None):
    """
    Create zip archive from content_dir

    Args:
        content_dir (str): The directory to compress the contents of
        arcname (str): archive name
        zipfilepath (str, optional): Path to create zipfile. Defaults to None.

    Returns:
        str: Returns the path of the zipfile created
    """
    if not zipfilepath:
        zipfilepath = content_dir + ".zip"
    with zipfile.ZipFile(zipfilepath, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.write(content_dir, arcname)
        for fn in os.listdir(content_dir):
            zf.write(
                os.path.join(content_dir, fn),
                os.path.join(os.path.basename(arcname), fn),
            )
    return zipfilepath


def _extract_archive(zip_file_path, extract_location):
    """
    Extract zipfile to <zip_file_path> and return the path to the directory containing
    the dicoms, which should be the zipfile name without the zip extension.

    Args:
        zip_file_path (str): Path of zipfile to extract
        extract_location (str): Path to extract zip file to

    Returns:
        str: extracted destination
    """
    if not zipfile.is_zipfile(zip_file_path):
        log.warning("%s is not a Zip File!", zip_file_path)
        return None

    with zipfile.ZipFile(zip_file_path) as ZF:
        if "/" in ZF.namelist()[0]:
            extract_dest = os.path.join(
                extract_location, ZF.namelist()[0].split("/")[0]
            )
            ZF.extractall(extract_location)
            return extract_dest
        else:
            extract_dest = os.path.join(
                extract_location, os.path.basename(zip_file_path).split(".zip")[0]
            )
            if not os.path.isdir(extract_dest):
                log.debug("Creating extract directory: %s", extract_dest)
                os.mkdir(extract_dest)
            log.debug("Extracting %s archive to: %s", zip_file_path, extract_dest)
            ZF.extractall(extract_dest)
            return extract_dest


def _export_files(fw, source_acquisition, dest_acquisition):
    """
    Export source_acquisition files to the exported acquisiton.

    For each file in the source_acquisition:
        1. Download the file
            a. If the file is a DICOM file, modify the DICOM archives individual files
               to match the appropriate metadata as exists in Flywheel.
        2. Upload the file to the dest_acquisition
        3. Modify the file in the dest_acquisition to have the same metadata

    Args:
        fw (flywheel.Client): Valid Flywheel Client
        source_acquisition (flywheel.Acquisition): Source Acquisition of files
        dest_acquisition (flywheel.Acquisition): Destination Acquisition of files
        map_fw_to_dcm (bool, optional): Not Used. Defaults to False.
    """

    # Get the source_acquisition so that the metadata are all there.
    source_acquisition = source_acquisition.reload()
    source_session = fw.get(source_acquisition.parents["session"])
    source_subject = fw.get(source_acquisition.parents["subject"])
    source_project = fw.get(source_acquisition.parents["project"])

    for acq_file in source_acquisition.files:
        log.info(
            "Exporting %s/%s/%s/%s/%s...",
            source_project.label,
            source_subject.label,
            source_session.label,
            source_acquisition.label,
            acq_file.name,
        )
        # The DICOM files are assumed to have been fully anonymized
        upload_file_path = os.path.join("/tmp", acq_file.name)
        acq_file.download(upload_file_path)

        # Upload the file to the dest_acquisition
        log.debug("Uploading %s to %s", acq_file.name, dest_acquisition.label)

        # Add logic around retrying failed uploads
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            status = dest_acquisition.upload_file(upload_file_path)
            log.info("Upload status = %s", status)
            # NOTE: Why do we do this? Can't we reload instead?
            dest_acquisition = fw.get_acquisition(dest_acquisition.id)
            file_names = [x.name for x in dest_acquisition.files]
            log.debug(file_names)
            if os.path.basename(upload_file_path) not in file_names:
                log.warning(
                    "Upload failed for %s - retrying...",
                    os.path.basename(upload_file_path),
                )
            else:
                log.info(
                    "Successfully exported: %s", os.path.basename(upload_file_path)
                )
                break

        # Delete the uploaded file locally.

        log.debug("Removing local file: %s", upload_file_path)
        os.remove(upload_file_path)

        # Update file metadata
        if acq_file.modality:
            log.debug(
                "Updating modality to %s for %s", acq_file.modality, acq_file.name
            )
            dest_acquisition.update_file(acq_file.name, modality=acq_file.modality)
        if not acq_file.modality and acq_file.name.endswith("mriqc.qa.html"):
            # Special case - mriqc output files do not have modality set, so
            # we must set the modality prior to the classification to avoid errors.
            dest_acquisition.update_file(acq_file.name, modality="MR")
        if acq_file.type:
            log.debug("Updating type to %s for %s", acq_file.type, acq_file.name)
            dest_acquisition.update_file(acq_file.name, type=acq_file.type)
        if acq_file.classification:
            log.debug(
                "Updating classification to %s for %s",
                acq_file.classification,
                acq_file.name,
            )
            dest_acquisition.update_file_classification(
                acq_file.name, acq_file.classification
            )
        if acq_file.info:
            log.debug("Updating info for %s", acq_file.name)
            dest_acquisition.update_file_info(acq_file.name, acq_file.info)

        dest_acquisition.reload()
