/*
 *  SPDX-FileCopyrightText: 2024 Krita developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef KIS_BRUSH_STROKE_PREVIEW_CACHE_H
#define KIS_BRUSH_STROKE_PREVIEW_CACHE_H

#include <QHash>
#include <QImage>
#include <QMutex>
#include <QSize>
#include <QString>
#include <QList>
#include <QSet>
#include <QObject>
#include <QThreadPool>

#include <kis_paintop_preset.h>
#include <kritaui_export.h>

/**
 * @brief Cache for brush stroke preview images
 *
 * This class provides a thread-safe LRU cache for storing
 * pre-generated stroke preview images. It helps improve
 * performance when displaying brush presets in stroke preview mode.
 *
 * Preview generation is done asynchronously to avoid blocking
 * the UI during paint events. When a preview is not cached,
 * a placeholder is returned and generation is scheduled.
 */
class KRITAUI_EXPORT KisBrushStrokePreviewCache : public QObject
{
    Q_OBJECT

public:
    /**
     * @brief Get the singleton instance
     */
    static KisBrushStrokePreviewCache* instance();

    /**
     * @brief Get cached preview or placeholder if not exists
     *
     * This method is non-blocking. If the preview is not cached,
     * it returns a placeholder and schedules background generation.
     * The previewReady signal will be emitted when generation completes.
     *
     * @param preset The brush preset
     * @param size The requested preview size
     * @return The cached preview image or a placeholder
     */
    QImage getPreview(KisPaintOpPresetSP preset, const QSize &size);

    /**
     * @brief Invalidate cache for a specific preset
     *
     * Call this when a preset's settings have changed.
     *
     * @param presetName The name of the preset to invalidate
     */
    void invalidatePreset(const QString &presetName);

    /**
     * @brief Clear the entire cache
     */
    void clearCache();

    /**
     * @brief Set maximum cache size (number of entries)
     *
     * @param size Maximum number of cache entries
     */
    void setMaxCacheSize(int size);

    /**
     * @brief Get current cache size
     *
     * @return Number of entries currently in cache
     */
    int cacheSize() const;

    /**
     * @brief Check if a preview is cached
     *
     * @param preset The brush preset
     * @param size The preview size
     * @return true if preview is cached
     */
    bool isCached(KisPaintOpPresetSP preset, const QSize &size) const;

    /**
     * @brief Pre-generate previews for all brush presets
     *
     * This should be called on startup to warm the cache and prevent
     * lag when scrolling through presets.
     *
     * @param size The preview size to generate
     */
    void preGenerateAllPreviews(const QSize &size);

Q_SIGNALS:
    /**
     * @brief Emitted when a preview has been generated
     *
     * Connect to this signal to trigger a repaint when previews are ready.
     *
     * @param presetName The name of the preset
     */
    void previewReady(const QString &presetName);

public Q_SLOTS:
    /**
     * @brief Handle completed preview generation
     */
    void onPreviewGenerated(const QString &key, const QString &presetName,
                            const QImage &preview);

private:
    KisBrushStrokePreviewCache();
    ~KisBrushStrokePreviewCache();

    // Disable copy
    KisBrushStrokePreviewCache(const KisBrushStrokePreviewCache&) = delete;
    KisBrushStrokePreviewCache& operator=(const KisBrushStrokePreviewCache&) = delete;

    /**
     * @brief Generate cache key from preset name and size
     */
    QString generateCacheKey(const QString &presetName, const QSize &size) const;

    /**
     * @brief Evict least recently used entries if cache is full
     */
    void evictIfNeeded();

    /**
     * @brief Update access order for LRU tracking
     */
    void updateAccessOrder(const QString &key);

    /**
     * @brief Generate a placeholder image
     */
    QImage generatePlaceholder(const QSize &size) const;

    /**
     * @brief Schedule background generation for a preset
     */
    void scheduleGeneration(KisPaintOpPresetSP preset, const QSize &size,
                            const QString &key);

    struct CacheEntry {
        QImage image;
    };

    mutable QMutex m_mutex;
    QHash<QString, CacheEntry> m_cache;
    QList<QString> m_accessOrder;  // For LRU eviction (front = oldest)
    QSet<QString> m_pendingGenerations;  // Keys currently being generated
    QSet<QString> m_preGeneratedSizes;   // Sizes that have been pre-generated
    int m_maxCacheSize;
    QThreadPool m_threadPool;  // Dedicated pool with limited threads

    static KisBrushStrokePreviewCache* s_instance;
};

#endif // KIS_BRUSH_STROKE_PREVIEW_CACHE_H
