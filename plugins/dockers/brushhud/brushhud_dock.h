/*
 *  SPDX-FileCopyrightText: 2009 Cyrille Berger <cberger@cberger.net>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

#ifndef _BRUSHHUD_DOCK_H_
#define _BRUSHHUD_DOCK_H_

#include "kis_brush_hud.h"
#include <QPointer>
#include <QDockWidget>
#include <QList>
#include <KoCanvasObserverBase.h>
#include <kis_canvas2.h>

class QStackedWidget;
class QScrollArea;
class QWidget;
class QVBoxLayout;
class KoCanvasController;

class BrushHudDock : public QDockWidget, public KoCanvasObserverBase {
    Q_OBJECT
public:
    BrushHudDock( );
    QString observerName() override { return "BrushHudDock"; }
    void setCanvas(KoCanvasBase *canvas) override;
    void unsetCanvas() override;

private Q_SLOTS:
    void slotToolChanged();
    void slotToolOptionWidgetsChanged(KoCanvasController *controller, const QList<QPointer<QWidget> > &widgets);

private:
    bool isFreehandBrushTool() const;
    void updateDockerContent();

private:
    QPointer<KisCanvas2> m_canvas;
    KisBrushHud* m_brushHud;
    QStackedWidget* m_stackedWidget;
    QWidget* m_toolOptionsContainer;
    QVBoxLayout* m_toolOptionsLayout;
    QScrollArea* m_toolOptionsScrollArea;
    QList<QPointer<QWidget> > m_currentToolOptionWidgets;
};


#endif