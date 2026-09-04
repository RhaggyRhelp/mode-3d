"""Addon Preferences for MoGe Splat Studio.

Configures Python interpreter, daemon port, and disk cache cleanup policy.
"""
from __future__ import annotations

import os
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import AddonPreferences

from .cleanup import get_cache_size_mb, MOGE_OT_purge_all_cache


class MoGeAddonPreferences(AddonPreferences):
    bl_idname = __package__

    daemon_python: StringProperty(
        name="Python Executable",
        description="Path to Python with PyTorch and MoGe dependencies",
        subtype='FILE_PATH',
        default="",
    )

    daemon_host: StringProperty(
        name="Daemon Host",
        description="Host address of the MoGe GPU daemon",
        default="127.0.0.1",
    )

    daemon_port: IntProperty(
        name="Daemon Port",
        description="Port for the MoGe GPU daemon",
        default=8766,
        min=1024,
        max=65535,
    )

    auto_cleanup: BoolProperty(
        name="Auto-Cleanup Disk Cache",
        description="Automatically remove previous scan payload files on each new scan",
        default=True,
    )

    auto_purge_datablocks: BoolProperty(
        name="Auto-Purge Unused Datablocks",
        description="Purge unreferenced MoGe meshes and materials when rescanning",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        # Daemon Configuration Box
        box = layout.box()
        box.label(text="GPU Daemon & Environment", icon='PREFERENCES')
        box.prop(self, "daemon_python")
        row = box.row()
        row.prop(self, "daemon_host")
        row.prop(self, "daemon_port")

        row_act = box.row(align=True)
        row_act.operator("moge_splat.ensure_daemon", text="Check Daemon Status", icon='CHECKMARK')
        row_act.operator("moge_splat.stop_daemon", text="Stop Daemon", icon='QUIT')

        # Storage & Self-Cleaning Box
        cbox = layout.box()
        cbox.label(text="Storage & Junk Control", icon='TRASH')
        cbox.prop(self, "auto_cleanup")
        cbox.prop(self, "auto_purge_datablocks")

        cache_mb = get_cache_size_mb()
        crow = cbox.row(align=True)
        crow.label(text=f"Current Disk Cache: {cache_mb:.1f} MB", icon='DISK_DRIVE')
        crow.operator("moge_splat.purge_all_cache", text="Purge Now", icon='TRASH')

        # Attribution / About Box
        abox = layout.box()
        abox.label(text="About & Upstream Credits", icon='INFO')
        abox.label(text="Based on MoGe / MoGe-3 (Microsoft Research & HKUST)")
        abox.label(text="Authors: Ruicheng Wang, Shengyi Qian, et al.")


def get_preferences(context=None) -> MoGeAddonPreferences | None:
    if context is None:
        context = bpy.context
    try:
        return context.preferences.addons[__package__].preferences
    except Exception:
        return None
