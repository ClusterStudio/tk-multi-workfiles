# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import tank
from tank import TankError
from tank.platform.qt import QtCore, QtGui 

from .wrapper_dialog import WrapperDialog
from .scene_operation import get_current_path, save_file, VERSION_UP_FILE_ACTION


class Versioning(object):
    """
    Main versioning functionality
    """
    
    @staticmethod
    def show_change_version_dlg(app):
        """
        Help method to show a dialog allowing the user to 
        change the version of the current work file        
        """
        handler = Versioning(app)
        handler._show_change_version_dlg()
        
    def __init__(self, app, work_template=None, publish_template=None, context=None):
        """
        Construction
        """
        self._app = app
        self._work_template = work_template if work_template else self._app.get_template("template_work")
        self._publish_template = publish_template if publish_template else self._app.get_template("template_publish")
        self._context = context if context else self._app.context
        
    def change_work_file_version(self, work_path, new_version):
        """
        Change the current work file version
        """
        if not "version" in self._work_template.keys:
            raise TankError("Work template does not contain a version key - unable to change version!")
        
        # update version and get new path:
        fields = self._work_template.get_fields(work_path)
        current_version = fields["version"]
        fields["version"] = new_version
        new_work_file = self._work_template.apply_fields(fields)
        
        # do save-as:
        save_file(self._app, VERSION_UP_FILE_ACTION, self._app.context, new_work_file)        

    def get_max_version(self, all_files, fields):
        """
        Get the next available version
        """
        # call out to hook to provide list of files:
        #all_files = self._app.execute_hook("hook_find_files", work_template=self._work_template, 
        #                               publish_template=self._publish_template, context=self._context)
        #if not all_files or not isinstance(all_files, dict):
        #    return (None, None)
            
        ## validate returned files:
        #for file_type in ["publish", "work"]:
        #    files = all_files.get(file_type, [])
        #    if files:
        #        files = [f for f in files if isinstance(f, dict) and "path" in f]
        #    all_files[file_type] = files

        # find max publish version:        
        publish_versions = []
        template_has_version = "version" in self._publish_template.keys
        for file in all_files["publish"]:
            version = file.get("version")
            if version == None:
                if template_has_version:
                    publish_fields = self._publish_template.get_fields(file["path"])
                    version = publish_fields.get("version", 0)
                else:
                    version = 0
            
            # ensure this actually matches the fields passed in:
            fields["version"] = version        
            if file["path"] == self._publish_template.apply_fields(fields):
                publish_versions.append(version)
                
        max_publish_version = max(publish_versions) if publish_versions else None
        
        # find max work version:
        work_versions = []
        template_has_version = "version" in self._work_template.keys 
        for file in all_files["work"]:
            version = file.get("version")
            if version == None:
                if template_has_version:
                    work_fields = self._work_template.get_fields(file["path"])
                    version = work_fields.get("version", 0)
                else:
                    version = 0
                    
            # ensure this actually matches the fields passed in:
            fields["version"] = version        
            if file["path"] == self._work_template.apply_fields(fields):                    
                work_versions.append(version)
                
        max_work_version = max(work_versions) if work_versions else None
           
        return (max_work_version, max_publish_version)
        
    def _show_change_version_dlg(self):
        """
        Show the change version dialog
        """
        try:
            work_path = get_current_path(self._app, VERSION_UP_FILE_ACTION, self._app.context) 
        except Exception, e:
            msg = ("Failed to get the current file path:\n\n"
                  "%s\n\n"
                  "Unable to continue!" % e)
            QtGui.QMessageBox.critical(None, "Change Version Error!", msg)
            return

        if not work_path or not self._work_template.validate(work_path):
            msg = ("Unable to Change Version!\n\nPlease save the scene as a valid work file before continuing")
            QtGui.QMessageBox.information(None, "Unable To Change Version!", msg)
            return

        if not "version" in self._work_template.keys:
            raise TankError("Work template does not contain a version key - unable to change version!")
        
        # use work template to get current version:
        fields = self._work_template.get_fields(work_path)
        current_version = fields.get("version")
        
        # get next available version:
        new_version = self._get_max_workfile_version(fields)+1
        
        while True:
            # show modal dialog:
            from .change_version_form import ChangeVersionForm
            form = ChangeVersionForm(current_version, new_version)
            try:
                dlg = WrapperDialog(form, "Change Version", form.geometry().size())
                res = dlg.exec_()
                
                if res == QtGui.QDialog.Accepted:
                    # get new version:
                    new_version = form.new_version
                    
                    if new_version == current_version:
                        QtGui.QMessageBox.information(None, "Version Error", "The new version (v%03d) must be different to the current version!" % new_version)
                        continue
                    
                    # validate:
                    msg = self._check_version_availability(work_path, new_version)
                    if msg:
                        msg = "<b>Warning: %s<b><br><br>Are you sure you want to change to this version?" % msg
                        res = QtGui.QMessageBox.question(None, "Confirm", msg, 
                                                         QtGui.QMessageBox.Cancel | QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                                                         QtGui.QMessageBox.No)
                        if res == QtGui.QMessageBox.No:
                            continue
                        elif res == QtGui.QMessageBox.Cancel:
                            break
                        
                    # ok, so change version:
                    try:
                        self.change_work_file_version(work_path, new_version)
                    except Exception, e:
                        QtGui.QMessageBox.critical(None, "Failure", "Version up of scene failed!\n\n%s" % e)
                        self._app.log_exception("Something went wrong while changing the version!")
                        continue

                    break
                else:                 
                    break
            finally:
                dlg.clean_up()
            
    #def _get_max_publish_version(self, fields):
    #    """
    #    Get the current highest publish version using the current
    #    context and the specified 'name' field.
    #    """
    #    # first, get paths and versions of all publishes for context:
    #    paths_and_versions = self._get_published_paths_and_versions_for_context(self._context)
    #    
    #    # now filter this list to find publishes that match the fields
    #    # passed in
    #    existing_publish_versions = []
    #    for p, pv in paths_and_versions:
    #        if not self._publish_template.validate(p):
    #            # path isn't valid for the template!
    #            continue
    #
    #        # want to make sure that all fields from the publish
    #        # path match those passed in (ignoring version!)
    #        publish_fields = self._publish_template.get_fields(p)
    #        
    #        for key in self._publish_template.keys:
    #            # enumerate through keys as we need to check for optional
    #            # keys which may be missing in one set of keys!
    #            in_fields = key in fields
    #            in_publish_fields = key in publish_fields
    #            
    #            if self._publish_template.is_optional(key):
    #                if in_fields != in_publish_fields:
    #                    # optional field in one set but not the other so not
    #                    # a valid match!
    #                    v = None
    #                    break
    #                elif not in_fields:
    #                    # optional key isn't in either sets of fields
    #                    # so this is a match!
    #                    continue
    #            else:
    #                if not in_fields:
    #                    # required key not in fields so definitely 
    #                    # not a match!
    #                    v=None
    #                    break
    #            
    #            if key == "version":
    #                # we want to keep track of versions:
    #                v = publish_fields[key]
    #                continue
    #            else:
    #                if fields[key] != publish_fields[key]:
    #                    # ok, this path doesn't match!
    #                    v = None
    #                    break
    #                    
    #        if v == None:
    #            # not a match!
    #            continue
    #        
    #        existing_publish_versions.append(v)
    #        if pv != None and v != pv:
    #            # this is a discrepancy in the data but can handle it by adding 
    #            # the version returned from Shotgun to the list as well! 
    #            existing_publish_versions.append(pv)
    #
    #    max_publish_version = max(existing_publish_versions) if existing_publish_versions else None
    #    return max_publish_version
            
            
    def _get_max_workfile_version(self, fields):
        """
        Get the current highest version of the work file that
        is generated using the current work template and the
        specified fields
        """
        # find max workfile version that exactly matches all other fields:
        work_area_paths = self._app.tank.paths_from_template(self._work_template, fields, ["version"])
        existing_work_versions = [self._work_template.get_fields(p).get("version") for p in work_area_paths]
        max_work_version = max(existing_work_versions) if existing_work_versions else None
        return max_work_version
          
    def _get_published_paths_and_versions_for_context(self, ctx):
        """
        Get list of published files for the current 
        context together with their version numbers
        """
        filters = [["entity", "is", ctx.entity]]
        if ctx.task:
            filters.append(["task", "is", ctx.task])
        
        published_file_entity_type = tank.util.get_published_file_entity_type(self._app.tank)
        sg_result = self._app.shotgun.find(published_file_entity_type, filters, ["path", "version_number"])
 
        paths_and_versions = []
        for res in sg_result:
            path = res.get("path", {}).get("local_path")
            if path:
                paths_and_versions.append((path, res.get("version_number")))
 
        return paths_and_versions           
                    
    def _check_version_availability(self, work_path, version):
        """
        Check to see if the specified version is already in use
        either as a work file or as a publish
        
        Note: this doesn't check for user sandboxes atm
        """
        if version == None or version < 0:
            return "'%d' is not a valid version number!" % version 
        
        # get fields for work file path:
        fields = self._work_template.get_fields(work_path)
        
        # check that version is actually different:
        if fields["version"] == version:
            return "The current work file is already version v%03d" % version

        # check to see if a work file of that version exists:        
        fields["version"] = version
        new_work_file = self._work_template.apply_fields(fields)
        if os.path.exists(new_work_file):
            return "Work file already exists for version v%03d - changing to this version will overwrite the existing file!" % version
        
        
        
        
        
        
        
        
        