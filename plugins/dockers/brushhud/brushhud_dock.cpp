/*
 *  SPDX-FileCopyrightText: 2009 Cyrille Berger <cberger@cberger.net>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "brushhud_dock.h"

#include <klocalizedstring.h>

#include <QStackedWidget>
#include <QScrollArea>
#include <QVBoxLayout>
#include <QWidget>

#include <KoCanvasResourceProvider.h>
#include <KoCanvasBase.h>
#include <KoToolManager.h>
#include <KoCanvasController.h>

#include "kis_brush_hud.h"
#include "kis_canvas2.h"
#include "KisViewManager.h"


BrushHudDock::BrushHudDock( )
    : QDockWidget(i18nc("@title:window On-Canvas Brush Editor docker", "On-Canvas Brush Editor"))
    , m_canvas(0)
    , m_brushHud(0)
    , m_stackedWidget(0)
    , m_toolOptionsContainer(0)
    , m_toolOptionsLayout(0)
    , m_toolOptionsScrollArea(0)
{
}

void BrushHudDock::setCanvas(KoCanvasBase *canvas)
{
    setEnabled(canvas != 0);

    if (m_canvas) {
        m_canvas->disconnectCanvasObserver(this);
        if (m_canvas->resourceManager()) {
            disconnect(m_canvas->resourceManager(), 0, this, 0);
        }
    }

    // Disconnect from KoToolManager signals
    disconnect(KoToolManager::instance(), 0, this, 0);

    m_canvas = dynamic_cast<KisCanvas2*>(canvas);

    if (m_canvas && m_canvas->viewManager() && m_canvas->resourceManager()) {
        // Create the stacked widget to switch between brush HUD and tool options
        if (!m_stackedWidget) {
            m_stackedWidget = new QStackedWidget(this);
            setWidget(m_stackedWidget);
        }

        // Create the brush HUD
        if (!m_brushHud) {
            m_brushHud = new KisBrushHud(m_canvas->viewManager()->canvasResourceProvider(), m_stackedWidget);
            m_stackedWidget->addWidget(m_brushHud);
        }

        // Create the tool options container
        if (!m_toolOptionsContainer) {
            m_toolOptionsScrollArea = new QScrollArea(m_stackedWidget);
            m_toolOptionsScrollArea->setFrameShape(QFrame::NoFrame);
            m_toolOptionsScrollArea->setWidgetResizable(true);
            m_toolOptionsScrollArea->setFocusPolicy(Qt::NoFocus);

            m_toolOptionsContainer = new QWidget(m_toolOptionsScrollArea);
            m_toolOptionsLayout = new QVBoxLayout(m_toolOptionsContainer);
            m_toolOptionsLayout->setContentsMargins(4, 4, 4, 0);
            m_toolOptionsLayout->setSpacing(2);

            m_toolOptionsScrollArea->setWidget(m_toolOptionsContainer);
            m_stackedWidget->addWidget(m_toolOptionsScrollArea);
        }

        // Connect to KoToolManager signals
        connect(KoToolManager::instance(), SIGNAL(changedTool(KoCanvasController*)),
                this, SLOT(slotToolChanged()));
        connect(KoToolManager::instance(), SIGNAL(toolOptionWidgetsChanged(KoCanvasController*,QList<QPointer<QWidget> >)),
                this, SLOT(slotToolOptionWidgetsChanged(KoCanvasController*,QList<QPointer<QWidget> >)));

        // Update the docker content based on the current tool
        updateDockerContent();
    }
    else {
        setWidget(nullptr);
    }
}

void BrushHudDock::unsetCanvas()
{
    if (m_canvas) {
        if (m_canvas->resourceManager()) {
            disconnect(m_canvas->resourceManager(), 0, this, 0);
        }
    }
    disconnect(KoToolManager::instance(), 0, this, 0);
    m_canvas = 0;
    setEnabled(false);
}

void BrushHudDock::slotToolChanged()
{
    // Ignore temporary tool changes from Canvas Input shortcuts
    if (KoToolManager::instance()->isTemporaryToolActive()) {
        return;
    }
    updateDockerContent();
}

void BrushHudDock::slotToolOptionWidgetsChanged(KoCanvasController *controller, const QList<QPointer<QWidget> > &widgets)
{
    if (!m_canvas || !m_canvas->canvasController() || m_canvas->canvasController() != controller) {
        return;
    }

    // Ignore temporary tool changes from Canvas Input shortcuts
    // This prevents temporary tool invocations (like Shift for Line Tool) from affecting the docker
    if (KoToolManager::instance()->isTemporaryToolActive()) {
        return;
    }

    // Clear existing tool option widgets
    while (m_toolOptionsLayout->count() > 0) {
        QLayoutItem *item = m_toolOptionsLayout->takeAt(0);
        if (item->widget()) {
            item->widget()->setParent(nullptr);
        }
        delete item;
    }
    m_currentToolOptionWidgets.clear();

    // Store the new tool option widgets
    m_currentToolOptionWidgets = widgets;

    // Add the new widgets to the layout
    for (QPointer<QWidget> widget : widgets) {
        if (!widget.isNull() && !widget->objectName().isEmpty()) {
            widget->setParent(m_toolOptionsContainer);
            m_toolOptionsLayout->addWidget(widget);
            widget->show();
        }
    }

    m_toolOptionsLayout->addStretch(1);

    // Update the docker content
    updateDockerContent();

    // Pass tool option widgets to the Brush HUD for freehand brush tools
    if (m_brushHud && isFreehandBrushTool()) {
        m_brushHud->setToolOptionWidgets(widgets);
    }
}

bool BrushHudDock::isFreehandBrushTool() const
{
    QString toolId = KoToolManager::instance()->activeToolId();

    // Check if it's a freehand brush tool
    // The freehand brush tool ID is "KritaShape/KisToolBrush"
    // Also check for other freehand tools like dyna and multihand
    // Eraser mode is considered as part of the freehand brush tool since
    // it's just a mode of the brush tool, not a separate tool
    return (toolId == "KritaShape/KisToolBrush" ||
            toolId == "KritaShape/KisToolDyna" ||
            toolId == "KritaShape/KisToolMultiBrush");
}

void BrushHudDock::updateDockerContent()
{
    if (!m_stackedWidget) {
        return;
    }

    if (isFreehandBrushTool()) {
        // Show the brush HUD
        m_stackedWidget->setCurrentWidget(m_brushHud);
    } else {
        // Show the tool options
        m_stackedWidget->setCurrentWidget(m_toolOptionsScrollArea);
    }
}