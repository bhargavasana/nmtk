import os
import logging
from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save, post_delete, post_save
from django.db.models.loading import cache
from django.core.files.storage import get_storage_class
from django.contrib.auth import get_user_model
from django.dispatch import receiver
import simplejson as json
import shutil
from registration.signals import user_activated
from NMTK_server.default_data.init_account import setupAccount
from django.core.mail import mail_managers

User=get_user_model()
logger = logging.getLogger(__name__)


@receiver(user_activated)
def post_activation_setup(sender, user, **kwargs):
    # Deactivate the user, since the admin now needs to approve the account.
    if user.is_active:
        #if user.datafile_set.count() == 0:
          #  setupAccount(user)
        if settings.ADMIN_APPROVAL_REQUIRED:
#             logger.debug('Deactivating account since approval is required')
            user.is_active=False
            
            mail_managers('User {0} requires activation'.format(user.username),
                        'Please go to the admin interface and activate the account (and notify the user)')
            user.save()
        # setup the account by populating it with any required "default" files.
        

@receiver(post_delete, sender=User)
def delete_user_data(sender, instance, **kwargs):
    '''
    When a user is removed, we must remove all their data files and results as
    well, since it's possible the UID for the user could get assigned to another
    user (depending on the backend used.)  Generally, inactivating a user is
    a better strategy than removing the user.
    '''
#     logger.debug('Got post delete for user %s (%s)', instance.username,
#                  instance.pk)
    user_file_path=os.path.join(settings.FILES_PATH, 'NMTK_server', 'files',
                                str(instance.pk))
#     logger.debug('Removing all files for user %s (%s)', instance.pk,
#                  user_file_path)
    shutil.rmtree(user_file_path, ignore_errors=True)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    from NMTK_server.models import UserPreference
    if created:
        setupAccount(instance)
        UserPreference.objects.create(user=instance,
                                      config=json.dumps({}))

def find_models_with_filefield(): 
    result = []
    for app in cache.get_apps():
        model_list = cache.get_models(app)
        for model in model_list:
            for field in model._meta.fields:
                if isinstance(field, models.FileField):
                    result.append(model)
                    break
    return result

def remove_old_files(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
    except instance.DoesNotExist:
        return

    for field in instance._meta.fields:
        if not isinstance(field, models.FileField):
            continue
        old_file = getattr(old_instance, field.name)
        new_file = getattr(instance, field.name)
        storage = old_file.storage
        if old_file and old_file != new_file and storage and storage.exists(old_file.name):
            try:
                storage.delete(old_file.name)
            except Exception:
                logger.exception("Unexpected exception while attempting to delete old file '%s'" % old_file.name)

def remove_files(sender, instance, **kwargs):
    for field in instance._meta.fields:
        if not isinstance(field, models.FileField):
            continue
        file_to_delete = getattr(instance, field.name)
        storage = file_to_delete.storage
        if file_to_delete and storage and storage.exists(file_to_delete.name):
            try:
                storage.delete(file_to_delete.name)
            except Exception:
                logger.exception("Unexpected exception while attempting to delete file '%s'" % file_to_delete.name)


for model in find_models_with_filefield():
    pre_save.connect(remove_old_files, sender=model)
    post_delete.connect(remove_files, sender=model)
