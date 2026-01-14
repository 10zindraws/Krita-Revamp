/*
 * SPDX-FileCopyrightText: 2025 Krita Developers
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifndef KIS_PAINTOP_PRESET_SESSION_STORAGE_H
#define KIS_PAINTOP_PRESET_SESSION_STORAGE_H

#include <QObject>
#include <QScopedPointer>
#include <KSharedConfig>

#include "kritaui_export.h"
#include "kis_types.h"

/**
 * @brief Stores brush preset tweaks persistently across Krita sessions
 *
 * This class manages the storage and retrieval of user modifications to brush
 * presets. When users tweak brush settings, those changes are saved to a
 * configuration file that persists across Krita restarts.
 *
 * The original preset settings remain intact on disk - this only stores the
 * modifications. When the user presses "Reload the brush preset", the session
 * tweaks for that preset are cleared and the original is restored.
 */
class KRITAUI_EXPORT KisPaintOpPresetSessionStorage : public QObject
{
    Q_OBJECT

public:
    /**
     * @return the singleton instance
     */
    static KisPaintOpPresetSessionStorage *instance();

    /**
     * Save the current state of a preset's settings to session storage.
     * This is called whenever preset settings are modified.
     *
     * @param preset The preset whose current settings should be saved
     */
    void saveTweaks(KisPaintOpPresetSP preset);

    /**
     * Load previously saved tweaks for a preset.
     * This is called when switching to a preset to restore any saved tweaks.
     *
     * @param preset The preset to load tweaks for
     * @return true if tweaks were found and loaded, false otherwise
     */
    bool loadTweaks(KisPaintOpPresetSP preset);

    /**
     * Check if a preset has any saved tweaks.
     *
     * @param preset The preset to check
     * @return true if there are saved tweaks for this preset
     */
    bool hasTweaks(KisPaintOpPresetSP preset) const;

    /**
     * Clear saved tweaks for a preset.
     * This is called when the user presses "Reload the brush preset" or
     * when a preset is saved/overwritten.
     *
     * @param preset The preset whose tweaks should be cleared
     */
    void clearTweaks(KisPaintOpPresetSP preset);

    /**
     * Force syncing the configuration to disk.
     */
    void sync();

Q_SIGNALS:
    /**
     * Emitted when preset tweaks are saved.
     * This signal is used by components that need to update when brush
     * settings are modified (like stroke preview cache invalidation).
     *
     * @param presetName The name of the preset whose tweaks were saved
     */
    void sigTweaksSaved(const QString &presetName);

    /**
     * Emitted when preset tweaks are cleared (preset reloaded to defaults).
     *
     * @param presetName The name of the preset whose tweaks were cleared
     */
    void sigTweaksCleared(const QString &presetName);

public:
    KisPaintOpPresetSessionStorage();
    ~KisPaintOpPresetSessionStorage() override;

private:
    KisPaintOpPresetSessionStorage(const KisPaintOpPresetSessionStorage &) = delete;
    KisPaintOpPresetSessionStorage &operator=(const KisPaintOpPresetSessionStorage &) = delete;

    /**
     * Generate a unique key for a preset in the config file.
     * Uses the resource ID and MD5 hash to uniquely identify the preset.
     */
    QString tweakKey(KisPaintOpPresetSP preset) const;

private:
    struct Private;
    const QScopedPointer<Private> m_d;
};

#endif // KIS_PAINTOP_PRESET_SESSION_STORAGE_H
