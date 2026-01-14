/*
 *  SPDX-FileCopyrightText: 2024 Krita developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef KIS_BRUSH_STROKE_PREVIEW_GENERATOR_H
#define KIS_BRUSH_STROKE_PREVIEW_GENERATOR_H

#include <QImage>
#include <QSize>
#include <QColor>
#include <QMutex>

#include <kis_paintop_preset.h>
#include <kis_types.h>
#include <kritaui_export.h>

class KoCanvasResourceProvider;

/**
 * @brief Generates stroke preview images for brush presets
 *
 * This class generates preview images showing how a brush stroke
 * will look with pressure variation from left (low pressure) to
 * right (high pressure). It reuses the algorithm from
 * KisPresetLivePreviewView but generates the preview synchronously.
 */
class KRITAUI_EXPORT KisBrushStrokePreviewGenerator
{
public:
    /**
     * @brief Generate a stroke preview image for a brush preset
     *
     * @param preset The brush preset to generate preview for
     * @param size The target image size (width should be larger than height for stroke preview)
     * @param backgroundColor Background color for the preview
     * @param foregroundColor Stroke color (default black)
     * @return QImage containing the stroke preview, or empty image on failure
     */
    static QImage generateStrokePreview(
        KisPaintOpPresetSP preset,
        const QSize &size = QSize(200, 60),
        const QColor &backgroundColor = QColor(200, 200, 200),
        const QColor &foregroundColor = Qt::black
    );

    /**
     * @brief Check if a brush preset supports stroke preview
     *
     * Some brush engines (roundmarker, experimentbrush, duplicate)
     * cannot render meaningful stroke previews.
     *
     * @param preset The brush preset to check
     * @return true if stroke preview is supported, false otherwise
     */
    static bool supportsStrokePreview(KisPaintOpPresetSP preset);

    /**
     * @brief Check if a brush preset needs striped background
     *
     * Some brush engines (colorsmudge, deformbrush, filter) work better
     * with a striped background to show their effects.
     *
     * @param preset The brush preset to check
     * @return true if striped background should be used
     */
    static bool needsStripedBackground(KisPaintOpPresetSP preset);

private:
    /**
     * @brief Paint the background for the stroke preview
     */
    static void paintBackground(
        KisPaintDeviceSP device,
        const QSize &size,
        const QColor &backgroundColor,
        bool striped
    );

    /**
     * @brief Paint the S-curve stroke
     */
    static void paintStroke(
        KisImageSP image,
        KisPaintLayerSP layer,
        KisPaintOpPresetSP preset,
        const QSize &size,
        const QColor &foregroundColor
    );

    /**
     * @brief Paint a wavy stroke for sketch/curve/particle brushes
     */
    static void paintWavyStroke(
        KisImageSP image,
        KisPaintLayerSP layer,
        KisPaintOpPresetSP preset,
        const QSize &size,
        const QColor &foregroundColor
    );

    static QMutex s_mutex;
};

#endif // KIS_BRUSH_STROKE_PREVIEW_GENERATOR_H
