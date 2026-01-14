/*
 * SPDX-FileCopyrightText: 2025 Krita Developers
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "KisPaintOpPresetSessionStorage.h"

#include <QGlobalStatic>
#include <QDomDocument>
#include <QStandardPaths>
#include <QDir>

#include <KSharedConfig>
#include <KConfigGroup>

#include <kis_debug.h>
#include <brushengine/kis_paintop_preset.h>
#include <brushengine/kis_paintop_settings.h>

Q_GLOBAL_STATIC(KisPaintOpPresetSessionStorage, s_instance)

struct KisPaintOpPresetSessionStorage::Private
{
    Private()
        : config(KSharedConfig::openConfig("presetTweaksrc"))
    {
    }

    KSharedConfigPtr config;
};

KisPaintOpPresetSessionStorage::KisPaintOpPresetSessionStorage()
    : m_d(new Private)
{
}

KisPaintOpPresetSessionStorage::~KisPaintOpPresetSessionStorage()
{
}

KisPaintOpPresetSessionStorage *KisPaintOpPresetSessionStorage::instance()
{
    return s_instance;
}

QString KisPaintOpPresetSessionStorage::tweakKey(KisPaintOpPresetSP preset) const
{
    if (!preset || preset->resourceId() < 0) {
        return QString();
    }

    // Use resource ID and MD5 to create a unique key
    // The MD5 helps distinguish if the preset was modified on disk
    QString md5 = preset->md5Sum(false);
    if (md5.isEmpty()) {
        // Fallback to just resource ID if no MD5
        return QString("Preset_%1").arg(preset->resourceId());
    }
    return QString("Preset_%1_%2").arg(preset->resourceId()).arg(md5);
}

void KisPaintOpPresetSessionStorage::saveTweaks(KisPaintOpPresetSP preset)
{
    if (!preset || !preset->settings() || preset->resourceId() < 0) {
        return;
    }

    QString key = tweakKey(preset);
    if (key.isEmpty()) {
        return;
    }

    // Serialize the preset settings to XML
    QDomDocument doc;
    QDomElement root = doc.createElement("PresetTweaks");
    doc.appendChild(root);

    preset->settings()->toXML(doc, root);

    QString settingsXml = doc.toString();

    KConfigGroup group = m_d->config->group(key);
    group.writeEntry("settings", settingsXml);
    group.writeEntry("name", preset->name());
    group.writeEntry("timestamp", QDateTime::currentDateTime().toString(Qt::ISODate));

    m_d->config->sync();

    dbgResources << "Saved tweaks for preset:" << preset->name() << "key:" << key;

    Q_EMIT sigTweaksSaved(preset->name());
}

bool KisPaintOpPresetSessionStorage::loadTweaks(KisPaintOpPresetSP preset)
{
    if (!preset || !preset->settings() || preset->resourceId() < 0) {
        return false;
    }

    QString key = tweakKey(preset);
    if (key.isEmpty()) {
        return false;
    }

    if (!m_d->config->hasGroup(key)) {
        return false;
    }

    KConfigGroup group = m_d->config->group(key);
    QString settingsXml = group.readEntry("settings", QString());

    if (settingsXml.isEmpty()) {
        return false;
    }

    // Parse the XML and apply settings
    QDomDocument doc;
    if (!doc.setContent(settingsXml)) {
        warnKrita << "Failed to parse saved preset tweaks for:" << preset->name();
        return false;
    }

    QDomElement root = doc.documentElement();
    if (root.isNull()) {
        return false;
    }

    // Apply the saved settings to the preset
    preset->settings()->fromXML(root);
    preset->setDirty(true);

    dbgResources << "Loaded tweaks for preset:" << preset->name() << "key:" << key;
    return true;
}

bool KisPaintOpPresetSessionStorage::hasTweaks(KisPaintOpPresetSP preset) const
{
    if (!preset || preset->resourceId() < 0) {
        return false;
    }

    QString key = tweakKey(preset);
    if (key.isEmpty()) {
        return false;
    }

    return m_d->config->hasGroup(key);
}

void KisPaintOpPresetSessionStorage::clearTweaks(KisPaintOpPresetSP preset)
{
    if (!preset || preset->resourceId() < 0) {
        return;
    }

    QString key = tweakKey(preset);
    if (key.isEmpty()) {
        return;
    }

    if (m_d->config->hasGroup(key)) {
        m_d->config->deleteGroup(key);
        m_d->config->sync();
        dbgResources << "Cleared tweaks for preset:" << preset->name() << "key:" << key;
        Q_EMIT sigTweaksCleared(preset->name());
    }
}

void KisPaintOpPresetSessionStorage::sync()
{
    m_d->config->sync();
}
