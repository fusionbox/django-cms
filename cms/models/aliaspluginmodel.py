# -*- coding: utf-8 -*-
from django.db import models
from django.db.models import Q
from django.utils.encoding import force_text, python_2_unicode_compatible

from cms.models import CMSPlugin, Placeholder


@python_2_unicode_compatible
class AliasPluginModel(CMSPlugin):
    cmsplugin_ptr = models.OneToOneField(CMSPlugin, related_name='cms_aliasplugin', parent_link=True)
    plugin = models.ForeignKey(CMSPlugin, editable=False, related_name="alias_reference", null=True)
    alias_placeholder = models.ForeignKey(Placeholder, editable=False, related_name="alias_placeholder", null=True)

    class Meta:
        app_label = 'cms'

    def __str__(self):
        if self.plugin_id:
            return "(%s) %s" % (force_text(self.plugin.get_plugin_name()), self.plugin.get_plugin_instance()[0])
        else:
            return force_text(self.alias_placeholder.get_label())

    def is_recursive(self):
        if self.plugin_id:
            placeholder = self.plugin.placeholder_id
        else:
            placeholder = self.alias_placeholder_id

        if not placeholder:
            return False

        plugins = AliasPluginModel.objects.filter(
            plugin_type='AliasPlugin',
            placeholder=placeholder,
        )
        plugins = plugins.filter(Q(plugin=self) | Q(alias_placeholder=self.placeholder_id))
        return plugins.exists()
