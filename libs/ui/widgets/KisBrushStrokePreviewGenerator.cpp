/*
 *  SPDX-FileCopyrightText: 2024 Krita developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "KisBrushStrokePreviewGenerator.h"

#include <QDebug>
#include <QPainter>
#include <QDomDocument>

#include <KoColorSpaceRegistry.h>
#include <KoColor.h>
#include <KoCompositeOpRegistry.h>

#include <kis_image.h>
#include <kis_paint_layer.h>
#include <kis_paint_device.h>
#include <kis_painter.h>
#include <kis_paint_information.h>
#include <kis_distance_information.h>
#include <kis_paintop_settings.h>
#include <kis_brush.h>
#include <KisResourcesInterface.h>
#include <KisRunnableStrokeJobData.h>
#include <KisFakeRunnableStrokeJobsExecutor.h>
#include <brushengine/kis_paintop.h>
#include <brushengine/kis_paintop_registry.h>
#include <brushengine/kis_random_source.h>
#include <brushengine/KisPerStrokeRandomSource.h>
#include <kis_transaction.h>
#include <KisInterstrokeDataFactory.h>
#include <KisInterstrokeDataTransactionWrapperFactory.h>

QMutex KisBrushStrokePreviewGenerator::s_mutex;

bool KisBrushStrokePreviewGenerator::supportsStrokePreview(KisPaintOpPresetSP preset)
{
    if (!preset) return false;

    const QString paintOpId = preset->paintOp().id();

    // These engines don't support stroke preview
    if (paintOpId == "roundmarker" ||
        paintOpId == "experimentbrush" ||
        paintOpId == "duplicate") {
        return false;
    }

    return true;
}

bool KisBrushStrokePreviewGenerator::needsStripedBackground(KisPaintOpPresetSP preset)
{
    if (!preset) return false;

    const QString paintOpId = preset->paintOp().id();

    // These engines benefit from striped backgrounds
    return (paintOpId == "colorsmudge" ||
            paintOpId == "deformbrush" ||
            paintOpId == "filter");
}

void KisBrushStrokePreviewGenerator::paintBackground(
    KisPaintDeviceSP device,
    const QSize &size,
    const QColor &backgroundColor,
    bool striped)
{
    const KoColorSpace *colorSpace = device->colorSpace();
    QRect bounds(QPoint(0, 0), size);

    if (striped) {
        // Paint alternating stripes for smudge/deform/filter brushes
        const int numStripes = 20;
        const float stripeWidth = static_cast<float>(size.width()) / numStripes;

        for (int i = 0; i < numStripes; i++) {
            KoColor fillColor(colorSpace);
            if (i % 2 == 0) {
                fillColor.fromQColor(QColor(80, 80, 80));
            } else {
                fillColor.fromQColor(QColor(140, 140, 140));
            }

            QRect stripeRect(
                static_cast<int>(i * stripeWidth), 0,
                static_cast<int>(stripeWidth) + 1, size.height()
            );

            // Direct fill without transaction (no undo needed for preview)
            device->fill(stripeRect, fillColor);
        }
    } else {
        // Solid background
        KoColor fillColor(colorSpace);
        fillColor.fromQColor(backgroundColor);

        // Direct fill without transaction (no undo needed for preview)
        device->fill(bounds, fillColor);
    }
}

/**
 * @brief Adjust spacing for predefined brush tips in stroke preview
 *
 * Predefined brushes (gbr, png, svg, abr) may have large spacing values that
 * cause gaps in small stroke previews. This function adjusts spacing to ensure
 * a visually pleasant preview.
 *
 * @param settings The paint op settings to modify (must have valid resourcesInterface)
 */
static void adjustPredefinedBrushSpacing(KisPaintOpSettingsSP settings)
{
    QString brushDefinition = settings->getString("brush_definition");
    if (brushDefinition.isEmpty()) {
        return;
    }

    QDomDocument d;
    d.setContent(brushDefinition, false);
    QDomElement element = d.firstChildElement("Brush");

    if (element.isNull()) {
        return;
    }

    QString brushType = element.attribute("type", "");

    // Only handle predefined brushes (not auto_brush)
    if (brushType.isEmpty() || brushType == "auto_brush") {
        return;
    }

    // Load the brush using the settings' resourcesInterface.
    // The preset should have been created with cloneWithResourcesSnapshot(),
    // which provides a local resources storage that is thread-safe.
    KisResourcesInterfaceSP resourcesInterface = settings->resourcesInterface();
    if (!resourcesInterface) {
        return;  // Can't load brush without resources interface
    }
    
    KisBrushSP brush = KisBrush::fromXML(element, resourcesInterface);

    if (!brush) {
        return;
    }

    // Adjust spacing for predefined brushes to avoid gaps in the stroke preview
    // If auto-spacing is off and spacing is too large, reduce it
    if (!brush->autoSpacingActive() && brush->spacing() > 0.15) {
        brush->setSpacing(0.1);

        // Write the modified brush back to settings
        d.clear();
        element = d.createElement("Brush");
        brush->toXML(d, element);
        d.appendChild(element);
        settings->setProperty("brush_definition", d.toString());
    }
}

void KisBrushStrokePreviewGenerator::paintStroke(
    KisImageSP image,
    KisPaintLayerSP layer,
    KisPaintOpPresetSP preset,
    const QSize &size,
    const QColor &foregroundColor)
{
    if (!preset || !preset->settings()) {
        return;
    }

    // Limit brush stroke size for preview
    qreal previewSize = qBound(3.0, preset->settings()->paintOpSize(), 25.0);

    // Exception for sketch and spray brushes
    const QString paintOpId = preset->paintOp().id();
    if (paintOpId == "sketchbrush" || paintOpId == "spraybrush") {
        previewSize = qMax(3.0, preset->settings()->paintOpSize());
    }

    // Clone the preset to avoid affecting the original.
    // Note: The caller (KisBrushStrokePreviewCache) should provide a preset
    // created with cloneWithResourcesSnapshot() for thread safety.
    // This clone is just to avoid modifying the caller's preset.
    KisPaintOpPresetSP proxyPreset = preset->clone().dynamicCast<KisPaintOpPreset>();
    if (!proxyPreset) {
        return;
    }
    
    KisPaintOpSettingsSP settings = proxyPreset->settings();
    if (!settings) {
        return;
    }

    // Set the brush size for preview
    settings->setPaintOpSize(previewSize);
    
    // Adjust spacing for predefined brushes to avoid gaps in stroke preview
    adjustPredefinedBrushSpacing(settings);

    // Limit texture size
    const int maxTextureSize = 200;
    int textureOffsetX = settings->getInt("Texture/Pattern/MaximumOffsetX") * 2;
    int textureOffsetY = settings->getInt("Texture/Pattern/MaximumOffsetY") * 2;
    double textureScale = settings->getDouble("Texture/Pattern/Scale");
    if (textureOffsetX * textureScale > maxTextureSize ||
        textureOffsetY * textureScale > maxTextureSize) {
        int maxSize = qMax(textureOffsetX, textureOffsetY);
        double result = static_cast<double>(maxTextureSize) / maxSize;
        settings->setProperty("Texture/Pattern/Scale", result);
    }

    // Handle spray brush scaling
    if (paintOpId == "spraybrush") {
        QDomElement element;
        QDomDocument d;
        QString brushDefinition = settings->getString("brush_definition");
        if (!brushDefinition.isEmpty()) {
            d.setContent(brushDefinition, false);
            element = d.firstChildElement("Brush");

            // Use settings' resourcesInterface for thread-safe brush loading
            KisResourcesInterfaceSP resourcesInterface = settings->resourcesInterface();
            KisBrushSP brush = resourcesInterface ? 
                KisBrush::fromXML(element, resourcesInterface) : nullptr;
            if (brush) {
                qreal width = brush->image().width();
                qreal scale = brush->scale();
                qreal diameterToBrushRatio = 1.0;
                qreal diameter = settings->getInt("Spray/diameter");

                if (brush->filename().endsWith(".svg", Qt::CaseInsensitive)) {
                    diameterToBrushRatio = diameter / (1000.0 * scale);
                    scale = 25.0 / 1000.0;
                } else {
                    if (width * scale > 25.0) {
                        diameterToBrushRatio = diameter / (width * scale);
                        scale = 25.0 / width;

                        if (!settings->getBool("SprayShape/proportional")) {
                            settings->setProperty("SprayShape/width",
                                qRound(scale * settings->getInt("SprayShape/width")));
                            settings->setProperty("SprayShape/height",
                                qRound(scale * settings->getInt("SprayShape/height")));
                        }
                    }
                }
                settings->setProperty("Spray/diameter", static_cast<int>(25.0 * diameterToBrushRatio));

                brush->setScale(scale);
                d.clear();
                element = d.createElement("Brush");
                brush->toXML(d, element);
                d.appendChild(element);
                settings->setProperty("brush_definition", d.toString());
            }
        }
    }

    proxyPreset->setSettings(settings);

    // Set up paint color
    KoColor paintColor(layer->paintDevice()->colorSpace());
    paintColor.fromQColor(foregroundColor);

    // Set up interstroke data for brushes that need it (like Color Smudge with Lightness mode)
    // This is required because Color Smudge uses interstroke data to store overlay devices
    QScopedPointer<KisInterstrokeDataFactory> interstrokeDataFactory(
        KisPaintOpRegistry::instance()->createInterstrokeDataFactory(proxyPreset));

    QScopedPointer<KisInterstrokeDataTransactionWrapperFactory> transactionWrapper;
    if (interstrokeDataFactory) {
        transactionWrapper.reset(new KisInterstrokeDataTransactionWrapperFactory(
            interstrokeDataFactory.take(), false));
    }

    // Create transaction that will set up interstroke data on the device
    QScopedPointer<KisTransaction> transaction(
        new KisTransaction(KUndo2MagicString(), layer->paintDevice(), nullptr, -1,
                           transactionWrapper.take()));

    // Setup painter
    KisPainter painter(layer->paintDevice());
    painter.setPaintColor(paintColor);
    // Use full painter opacity for previews; per-stroke strength is encoded in the preset.
    painter.setOpacityF(1.0);
    painter.setPaintOpPreset(proxyPreset, layer, image);

    // Calculate stroke path coordinates
    const qreal centerX = size.width() * 0.5;
    const qreal centerY = size.height() * 0.5;

    // Create random sources for paint information objects to avoid
    // "Accessing uninitialized random source!" warnings during preview generation
    KisRandomSourceSP randomSource = new KisRandomSource();
    KisPerStrokeRandomSourceSP perStrokeRandomSource = new KisPerStrokeRandomSource();

    // S-curve start point (left side, low pressure)
    KisPaintInformation startPoint;
    startPoint.setPos(QPointF(centerX - (size.width() * 0.45),
                              centerY + (size.height() * 0.2)));
    startPoint.setPressure(0.0);
    startPoint.setRandomSource(randomSource);
    startPoint.setPerStrokeRandomSource(perStrokeRandomSource);

    // S-curve end point (right side, high pressure)
    KisPaintInformation endPoint;
    endPoint.setPos(QPointF(centerX + (size.width() * 0.4),
                            centerY - (size.height() * 0.2)));
    endPoint.setPressure(1.0);
    endPoint.setRandomSource(randomSource);
    endPoint.setPerStrokeRandomSource(perStrokeRandomSource);

    // Set time for MyPaint brushes
    if (paintOpId == "mypaintbrush") {
        startPoint.setCurrentTime(123);
        endPoint.setCurrentTime(1230);
    }

    // Control points for S-curve bezier
    QPointF controlPoint1(centerX, centerY - size.height());
    QPointF controlPoint2(centerX, centerY + size.height());

    // Color Smudge brushes skip the first dab to initialize m_lastPaintPos,
    // so we need a warm-up stroke to make them paint properly.
    // Paint a single point at the start to prime the brush.
    if (paintOpId == "colorsmudge") {
        KisDistanceInformation warmupDistance;
        painter.paintAt(startPoint, &warmupDistance);
    }

    // Paint the bezier curve directly
    KisDistanceInformation currentDistance;
    painter.paintBezierCurve(startPoint, controlPoint1, controlPoint2, endPoint, &currentDistance);

    // For brushes that use asynchronous updates (like Pixel engine),
    // we need to flush the dab queue by calling doAsynchronousUpdate()
    if (proxyPreset->settings()->needsAsynchronousUpdates() && painter.paintOp()) {
        QVector<KisRunnableStrokeJobData*> jobs;
        painter.paintOp()->doAsynchronousUpdate(jobs);

        // Execute all the jobs synchronously using fake executor
        // AllowBarrierJobs is needed because the dab rendering may use barrier jobs
        KisFakeRunnableStrokeJobsExecutor executor(KisFakeRunnableStrokeJobsExecutor::AllowBarrierJobs);
        QVector<KisRunnableStrokeJobDataBase*> baseJobs;
        for (auto job : jobs) {
            baseJobs.append(job);
        }
        if (!baseJobs.isEmpty()) {
            executor.addRunnableJobs(baseJobs);
        }
    }

    painter.end();

    // End the transaction (we don't need the undo command for preview)
    delete transaction->endAndTake();
}

void KisBrushStrokePreviewGenerator::paintWavyStroke(
    KisImageSP image,
    KisPaintLayerSP layer,
    KisPaintOpPresetSP preset,
    const QSize &size,
    const QColor &foregroundColor)
{
    if (!preset || !preset->settings()) {
        return;
    }

    // Similar to paintStroke but with wavy pattern for sketch/curve/particle brushes
    qreal previewSize = qMax(3.0, preset->settings()->paintOpSize());

    // Clone the preset to avoid affecting the original.
    // Note: The caller (KisBrushStrokePreviewCache) should provide a preset
    // created with cloneWithResourcesSnapshot() for thread safety.
    KisPaintOpPresetSP proxyPreset = preset->clone().dynamicCast<KisPaintOpPreset>();
    if (!proxyPreset) {
        return;
    }
    
    KisPaintOpSettingsSP settings = proxyPreset->settings();
    if (!settings) {
        return;
    }

    // Set the brush size for preview
    settings->setPaintOpSize(previewSize);
    
    // Adjust spacing for predefined brushes to avoid gaps in stroke preview
    adjustPredefinedBrushSpacing(settings);

    proxyPreset->setSettings(settings);

    // Set up paint color
    KoColor paintColor(layer->paintDevice()->colorSpace());
    paintColor.fromQColor(foregroundColor);

    // Set up interstroke data for brushes that need it (like Color Smudge with Lightness mode)
    QScopedPointer<KisInterstrokeDataFactory> interstrokeDataFactory(
        KisPaintOpRegistry::instance()->createInterstrokeDataFactory(proxyPreset));

    QScopedPointer<KisInterstrokeDataTransactionWrapperFactory> transactionWrapper;
    if (interstrokeDataFactory) {
        transactionWrapper.reset(new KisInterstrokeDataTransactionWrapperFactory(
            interstrokeDataFactory.take(), false));
    }

    // Create transaction that will set up interstroke data on the device
    QScopedPointer<KisTransaction> transaction(
        new KisTransaction(KUndo2MagicString(), layer->paintDevice(), nullptr, -1,
                           transactionWrapper.take()));

    // Setup painter
    KisPainter painter(layer->paintDevice());
    painter.setPaintColor(paintColor);
    // Use full painter opacity for previews; per-stroke strength is encoded in the preset.
    painter.setOpacityF(1.0);
    painter.setPaintOpPreset(proxyPreset, layer, image);

    // Wavy stroke coordinates
    const qreal centerX = size.width() * 0.5;
    const qreal centerY = size.height() * 0.5;
    const qreal startX = centerX - (size.width() * 0.4);
    const qreal endX = centerX + (size.width() * 0.4);
    const int repeats = 8;

    // Create random sources for paint information objects to avoid
    // "Accessing uninitialized random source!" warnings during preview generation
    KisRandomSourceSP randomSource = new KisRandomSource();
    KisPerStrokeRandomSourceSP perStrokeRandomSource = new KisPerStrokeRandomSource();

    KisPaintInformation pointOne;
    pointOne.setPressure(0.0);
    pointOne.setPos(QPointF(startX, centerY));
    pointOne.setRandomSource(randomSource);
    pointOne.setPerStrokeRandomSource(perStrokeRandomSource);

    KisPaintInformation pointTwo;
    pointTwo.setPressure(0.0);
    pointTwo.setPos(QPointF(startX, centerY));
    pointTwo.setRandomSource(randomSource);
    pointTwo.setPerStrokeRandomSource(perStrokeRandomSource);

    KisDistanceInformation currentDistance;

    for (int i = 0; i < repeats; i++) {
        pointOne.setPos(pointTwo.pos());
        pointOne.setPressure(pointTwo.pressure());

        pointTwo.setPressure(static_cast<qreal>(i + 1) / repeats);
        qreal xPos = (static_cast<qreal>(i + 1) / repeats) * (endX - startX) + startX;
        pointTwo.setPos(QPointF(xPos, centerY));

        qreal offset = (size.height() / (repeats * 1.5)) * (i + 1);
        qreal handleY = centerY + offset;
        if (i % 2 == 0) {
            handleY = centerY - offset;
        }

        painter.paintBezierCurve(pointOne,
            QPointF(pointOne.pos().x(), handleY),
            QPointF(pointTwo.pos().x(), handleY),
            pointTwo,
            &currentDistance);
    }

    // For brushes that use asynchronous updates (like Pixel engine),
    // we need to flush the dab queue by calling doAsynchronousUpdate()
    if (proxyPreset->settings()->needsAsynchronousUpdates() && painter.paintOp()) {
        QVector<KisRunnableStrokeJobData*> jobs;
        painter.paintOp()->doAsynchronousUpdate(jobs);

        // Execute all the jobs synchronously using fake executor
        // AllowBarrierJobs is needed because the dab rendering may use barrier jobs
        KisFakeRunnableStrokeJobsExecutor executor(KisFakeRunnableStrokeJobsExecutor::AllowBarrierJobs);
        QVector<KisRunnableStrokeJobDataBase*> baseJobs;
        for (auto job : jobs) {
            baseJobs.append(job);
        }
        if (!baseJobs.isEmpty()) {
            executor.addRunnableJobs(baseJobs);
        }
    }

    painter.end();

    // End the transaction (we don't need the undo command for preview)
    delete transaction->endAndTake();
}

QImage KisBrushStrokePreviewGenerator::generateStrokePreview(
    KisPaintOpPresetSP preset,
    const QSize &size,
    const QColor &backgroundColor,
    const QColor &foregroundColor)
{
    if (!preset || !preset->settings() || size.isEmpty()) {
        return QImage();
    }

    // Lock to ensure thread safety
    QMutexLocker locker(&s_mutex);

    // Check if this preset supports stroke preview
    if (!supportsStrokePreview(preset)) {
        // Return a fallback image with "No Preview" text
        QImage fallback(size, QImage::Format_ARGB32_Premultiplied);
        fallback.fill(backgroundColor);

        QPainter painter(&fallback);
        painter.setPen(foregroundColor);
        QFont font;
        font.setPixelSize(qMin(size.height() / 3, 12));
        painter.setFont(font);
        painter.drawText(fallback.rect(), Qt::AlignCenter, "No Preview");
        painter.end();

        return fallback;
    }

    // Create a temporary image and paint layer
    const KoColorSpace *colorSpace = KoColorSpaceRegistry::instance()->rgb8();
    KisImageSP image = new KisImage(nullptr, size.width(), size.height(),
                                    colorSpace, "stroke_preview_image");
    KisPaintLayerSP backgroundLayer = new KisPaintLayer(image, "stroke_bg_layer",
                                                        OPACITY_OPAQUE_U8, colorSpace);
    KisPaintLayerSP strokeLayer = new KisPaintLayer(image, "stroke_layer",
                                                    OPACITY_OPAQUE_U8, colorSpace);

    // Paint background
    const bool striped = needsStripedBackground(preset);
    paintBackground(backgroundLayer->paintDevice(), size, backgroundColor, striped);

    // Ensure stroke layer starts transparent
    strokeLayer->paintDevice()->clear();

    // Determine stroke color (white for striped backgrounds)
    QColor strokeColor = striped ? Qt::white : foregroundColor;

    // Opacity should behave as stroke transparency (like in KisPresetLivePreviewView):
    // paint the stroke at full opacity and apply opacity as a final blend step.
    const qreal strokeOpacity = qBound<qreal>(0.0, preset->settings()->paintOpOpacity(), 1.0);

    // Flow should behave as the classic "stroke strength" (old opacity-like behavior).
    // Historically, the thumbnail strength was driven by the preset's OpacityValue during stroke rendering.
    // To keep Opacity as true transparency, we map FlowValue -> OpacityValue for the render preset,
    // while preserving FlowValue itself (do not force it).
    const qreal flowStrength = qBound<qreal>(0.0, preset->settings()->paintOpFlow(), 1.0);

    KisPaintOpPresetSP opaquePreset = preset->clone().dynamicCast<KisPaintOpPreset>();
    if (!opaquePreset || !opaquePreset->settings()) {
        return QImage();
    }
    opaquePreset->settings()->setPaintOpOpacity(flowStrength);

    // Paint the stroke
    const QString paintOpId = preset->paintOp().id();
    if (paintOpId == "sketchbrush" ||
        paintOpId == "curvebrush" ||
        paintOpId == "particlebrush") {
        paintWavyStroke(image, strokeLayer, opaquePreset, size, strokeColor);
    } else {
        paintStroke(image, strokeLayer, opaquePreset, size, strokeColor);
    }

    // Convert paint devices to QImage and blend stroke with requested opacity.
    QImage result = backgroundLayer->paintDevice()->convertToQImage(nullptr, image->bounds())
                        .convertToFormat(QImage::Format_ARGB32_Premultiplied);
    QImage strokeImg = strokeLayer->paintDevice()->convertToQImage(nullptr, image->bounds())
                           .convertToFormat(QImage::Format_ARGB32_Premultiplied);

    if (!strokeImg.isNull() && strokeOpacity < 1.0) {
        QPainter p(&result);
        p.setCompositionMode(QPainter::CompositionMode_SourceOver);
        p.setOpacity(strokeOpacity);
        p.drawImage(0, 0, strokeImg);
        p.end();
    } else if (!strokeImg.isNull()) {
        QPainter p(&result);
        p.setCompositionMode(QPainter::CompositionMode_SourceOver);
        p.drawImage(0, 0, strokeImg);
        p.end();
    }

    return result;
}
