/*
 *  SPDX-FileCopyrightText: 2024 Krita developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "KisBrushStrokePreviewCache.h"
#include "KisBrushStrokePreviewGenerator.h"

#include <QDebug>
#include <QThreadPool>
#include <QRunnable>
#include <QPainter>

#include <kis_paintop_settings.h>
#include <KisResourceModelProvider.h>
#include <KisResourceTypes.h>
#include <KisResourceModel.h>
#include <KisGlobalResourcesInterface.h>

#include <KisPaintOpPresetSessionStorage.h>

/**
 * @brief Runnable for background preview generation
 */
class PreviewGenerationRunnable : public QRunnable
{
public:
    PreviewGenerationRunnable(KisPaintOpPresetSP preset, const QSize &size,
                              const QString &key,
                              KisBrushStrokePreviewCache *cache)
        : m_size(size)
        , m_key(key)
        , m_cache(cache)
    {
        // Use cloneWithResourcesSnapshot to create a thread-safe clone.
        // This loads all linked resources (brushes, patterns, etc.) from the database
        // on the current (GUI) thread and embeds them in a local storage.
        // Without this, background threads would try to access the database,
        // which fails because QSqlDatabase connections are thread-specific.
        m_preset = preset->cloneWithResourcesSnapshot(
            KisGlobalResourcesInterface::instance(), nullptr, nullptr);

        // Apply any session-level tweaks (opacity/flow sliders etc.) so the generated
        // stroke preview matches what the user currently has in the brush settings.
        // This is needed because the preset objects coming from the resource model
        // represent on-disk state and do not include session tweaks.
        KisPaintOpPresetSessionStorage::instance()->loadTweaks(m_preset);
    }

    void run() override
    {
        if (!m_preset) return;

        QImage preview = KisBrushStrokePreviewGenerator::generateStrokePreview(
            m_preset, m_size,
            QColor(0x53, 0x53, 0x53),  // Background #535353
            Qt::white                   // Foreground (white stroke)
        );

        // Use queued connection to safely update cache from main thread
        QMetaObject::invokeMethod(m_cache, "onPreviewGenerated",
                                  Qt::QueuedConnection,
                                  Q_ARG(QString, m_key),
                                  Q_ARG(QString, m_preset->name()),
                                  Q_ARG(QImage, preview));
    }

private:
    KisPaintOpPresetSP m_preset;
    QSize m_size;
    QString m_key;
    KisBrushStrokePreviewCache *m_cache;
};

KisBrushStrokePreviewCache* KisBrushStrokePreviewCache::s_instance = nullptr;

KisBrushStrokePreviewCache* KisBrushStrokePreviewCache::instance()
{
    if (!s_instance) {
        s_instance = new KisBrushStrokePreviewCache();
    }
    return s_instance;
}

KisBrushStrokePreviewCache::KisBrushStrokePreviewCache()
    : QObject(nullptr)
    , m_maxCacheSize(500)  // Default: cache up to 500 previews
{
    // Configure dedicated thread pool with limited threads to avoid lag
    // Use only 2 threads to keep generation smooth without blocking UI
    m_threadPool.setMaxThreadCount(2);
}

KisBrushStrokePreviewCache::~KisBrushStrokePreviewCache()
{
}

QString KisBrushStrokePreviewCache::generateCacheKey(const QString &presetName, const QSize &size) const
{
    return QString("%1_%2x%3").arg(presetName).arg(size.width()).arg(size.height());
}

void KisBrushStrokePreviewCache::evictIfNeeded()
{
    // Remove oldest entries until we're under the limit
    while (m_cache.size() >= m_maxCacheSize && !m_accessOrder.isEmpty()) {
        QString oldestKey = m_accessOrder.takeFirst();
        m_cache.remove(oldestKey);
    }
}

void KisBrushStrokePreviewCache::updateAccessOrder(const QString &key)
{
    // Move key to end of access order (most recently used)
    m_accessOrder.removeAll(key);
    m_accessOrder.append(key);
}

QImage KisBrushStrokePreviewCache::getPreview(KisPaintOpPresetSP preset, const QSize &size)
{
    if (!preset || size.isEmpty()) {
        return QImage();
    }

    QMutexLocker locker(&m_mutex);

    const QString key = generateCacheKey(preset->name(), size);

    // Check if we have a cached entry
    if (m_cache.contains(key)) {
        updateAccessOrder(key);
        return m_cache[key].image;
    }

    // Check if generation is already pending
    if (m_pendingGenerations.contains(key)) {
        // Return placeholder while waiting
        return generatePlaceholder(size);
    }

    // Schedule background generation
    scheduleGeneration(preset, size, key);

    // Return placeholder immediately (non-blocking)
    return generatePlaceholder(size);
}

QImage KisBrushStrokePreviewCache::generatePlaceholder(const QSize &size) const
{
    QImage placeholder(size, QImage::Format_ARGB32_Premultiplied);
    placeholder.fill(QColor(0x53, 0x53, 0x53));  // #535353

    QPainter painter(&placeholder);
    painter.setPen(QColor(0xFF, 0xFF, 0xFF));  // Bright white brush name
    QFont font;
    font.setPixelSize(qMin(size.height() / 4, 10));
    painter.setFont(font);
    painter.drawText(placeholder.rect(), Qt::AlignCenter, "...");
    painter.end();

    return placeholder;
}

void KisBrushStrokePreviewCache::scheduleGeneration(KisPaintOpPresetSP preset, const QSize &size,
                                                     const QString &key)
{
    // Limit concurrent pending generations to avoid overwhelming the system
    const int maxPendingGenerations = 50;
    if (m_pendingGenerations.size() >= maxPendingGenerations) {
        // Too many pending, skip this one for now (will be retried on next paint)
        return;
    }

    // Mark as pending
    m_pendingGenerations.insert(key);

    // Create and queue the runnable
    PreviewGenerationRunnable *runnable = new PreviewGenerationRunnable(
        preset, size, key, this);
    runnable->setAutoDelete(true);

    // Use dedicated thread pool with limited threads to avoid system lag
    m_threadPool.start(runnable, QThread::LowPriority);
}

void KisBrushStrokePreviewCache::onPreviewGenerated(const QString &key, const QString &presetName,
                                                     const QImage &preview)
{
    {
        QMutexLocker locker(&m_mutex);

        // Remove from pending
        m_pendingGenerations.remove(key);

        // Store in cache if not already there
        if (!m_cache.contains(key)) {
            evictIfNeeded();

            CacheEntry entry;
            entry.image = preview;

            m_cache.insert(key, entry);
            m_accessOrder.append(key);
        }
    }

    // Notify that preview is ready (triggers view update)
    emit previewReady(presetName);
}

void KisBrushStrokePreviewCache::invalidatePreset(const QString &presetName)
{
    QMutexLocker locker(&m_mutex);

    // Remove all entries for this preset (at any size)
    QList<QString> keysToRemove;
    for (auto it = m_cache.constBegin(); it != m_cache.constEnd(); ++it) {
        if (it.key().startsWith(presetName + "_")) {
            keysToRemove.append(it.key());
        }
    }

    for (const QString &key : keysToRemove) {
        m_cache.remove(key);
        m_accessOrder.removeAll(key);
    }
}

void KisBrushStrokePreviewCache::clearCache()
{
    QMutexLocker locker(&m_mutex);
    m_cache.clear();
    m_accessOrder.clear();
}

void KisBrushStrokePreviewCache::setMaxCacheSize(int size)
{
    QMutexLocker locker(&m_mutex);
    m_maxCacheSize = qMax(1, size);

    // Evict if we're now over the limit
    while (m_cache.size() > m_maxCacheSize && !m_accessOrder.isEmpty()) {
        QString oldestKey = m_accessOrder.takeFirst();
        m_cache.remove(oldestKey);
    }
}

int KisBrushStrokePreviewCache::cacheSize() const
{
    QMutexLocker locker(&m_mutex);
    return m_cache.size();
}

bool KisBrushStrokePreviewCache::isCached(KisPaintOpPresetSP preset, const QSize &size) const
{
    if (!preset || size.isEmpty()) {
        return false;
    }

    QMutexLocker locker(&m_mutex);

    const QString key = generateCacheKey(preset->name(), size);
    return m_cache.contains(key);
}

void KisBrushStrokePreviewCache::preGenerateAllPreviews(const QSize &size)
{
    if (size.isEmpty()) {
        return;
    }

    // Check if we've already pre-generated for this size
    const QString sizeKey = QString("%1x%2").arg(size.width()).arg(size.height());
    {
        QMutexLocker locker(&m_mutex);
        if (m_preGeneratedSizes.contains(sizeKey)) {
            // Already pre-generated for this size, skip
            return;
        }
        // Mark as pre-generated to prevent duplicate runs
        m_preGeneratedSizes.insert(sizeKey);
    }

    // Get all brush presets from the resource model
    KisAllResourcesModel *model = KisResourceModelProvider::resourceModel(ResourceType::PaintOpPresets);
    if (!model) {
        return;
    }

    const int rowCount = model->rowCount();
    for (int i = 0; i < rowCount; ++i) {
        QModelIndex idx = model->index(i, 0);
        KoResourceSP resource = model->resourceForIndex(idx);
        KisPaintOpPresetSP preset = resource.dynamicCast<KisPaintOpPreset>();

        if (preset) {
            const QString key = generateCacheKey(preset->name(), size);

            QMutexLocker locker(&m_mutex);
            // Only schedule if not already cached and not already pending
            if (!m_cache.contains(key) && !m_pendingGenerations.contains(key)) {
                scheduleGeneration(preset, size, key);
            }
        }
    }
}
