/*
 *  SPDX-FileCopyrightText: 2020 Mathias Wein <lynx.mw+kde@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-3.0-or-later
 */
#include "WGSelectorPopup.h"

#include <QApplication>
#include <QBoxLayout>
#include <QCursor>
#include <QDesktopWidget>
#include <QPainter>
#include <QScreen>
#include <QTabletEvent>

#include <kis_global.h>
#include <KisVisualColorSelector.h>
#include <WGSelectorWidgetBase.h>
#include <WGShadeSelector.h>

WGSelectorPopup::WGSelectorPopup(QWidget *parent)
    : QWidget(parent, Qt::Popup | Qt::FramelessWindowHint), m_hideTimer(new QTimer(this))
{
    setAttribute(Qt::WA_TranslucentBackground);
    // Prevent tablet events from being captured by the canvas, ensuring
    // immediate responsiveness when dragging with pen tablets
    setAttribute(Qt::WA_NoMousePropagation, true);
    QBoxLayout *lo = new QBoxLayout(QBoxLayout::LeftToRight, this);
    lo->setObjectName("WGSelectorPopupLayout");
    lo->setSizeConstraint(QLayout::SetFixedSize);
    lo->setMargin(m_margin);
    m_hideTimer->setSingleShot(true);
    m_hideTimer->setInterval(50);
    connect(m_hideTimer, SIGNAL(timeout()), this, SLOT(hide()));

}

void WGSelectorPopup::setSelectorWidget(KisVisualColorSelector *selector)
{
    replaceCentranWidget(selector);
    connect(selector, SIGNAL(sigInteraction(bool)), SLOT(slotInteraction(bool)));
    m_selectorWidget = 0;
}

void WGSelectorPopup::setSelectorWidget(WGSelectorWidgetBase *selector)
{
    replaceCentranWidget(selector);
    connect(selector, SIGNAL(sigColorInteraction(bool)), SLOT(slotInteraction(bool)));
    m_selectorWidget = selector;
}

WGSelectorWidgetBase *WGSelectorPopup::selectorWidget() const
{
    return m_selectorWidget;
}

void WGSelectorPopup::slotShowPopup()
{
    QPoint cursorPos = QCursor::pos();
    QScreen *activeScreen = 0;
#if (QT_VERSION >= QT_VERSION_CHECK(5, 10, 0))
    activeScreen = QGuiApplication::screenAt(cursorPos);
#endif
    const QRect availRect = (activeScreen)? activeScreen->availableGeometry() : QApplication::desktop()->availableGeometry(this);

    QRect popupRect(geometry());
    QPoint offset = m_selectorWidget ? m_selectorWidget->pos() + m_selectorWidget->popupOffset()
                                     : popupRect.center() - popupRect.topLeft();

    popupRect.moveTopLeft(cursorPos - offset);
    popupRect = kisEnsureInRect(popupRect, availRect);


    move(popupRect.topLeft());

    show();
    //m_colorPreviewPopup->show();
}

void WGSelectorPopup::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event);
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);
    painter.setBrush(palette().window());
    painter.drawRoundedRect(QRect(0, 0, width(), height()), m_margin, m_margin);
}


void WGSelectorPopup::enterEvent(QEvent *event)
{
    Q_UNUSED(event);
    if (m_hideTimer->isActive())  {
        m_hideTimer->stop();
    }
}

void WGSelectorPopup::leaveEvent(QEvent *event)
{
    Q_UNUSED(event);

    if (!m_isInteracting) {
        m_hideTimer->start();
    }
}

void WGSelectorPopup::keyPressEvent(QKeyEvent *event)
{
    Q_UNUSED(event);
    hide();
}

void WGSelectorPopup::hideEvent(QHideEvent *event)
{
    QWidget::hideEvent(event);
    Q_EMIT sigPopupClosed(this);
}

void WGSelectorPopup::slotInteraction(bool active)
{
    m_isInteracting = active;
    if (!active && !underMouse()) {
        hide();
    }
}

void WGSelectorPopup::tabletEvent(QTabletEvent *event)
{
    // For Qt::Popup windows, tablet events may be delayed due to special input
    // handling. Actively forward tablet events to the child widget under the
    // cursor for immediate responsiveness.
    QPoint eventPos = event->pos();
    QWidget *child = childAt(eventPos);
    if (child) {
        // Find the deepest child widget at this position
        QPoint childPos = child->mapFrom(this, eventPos);
        QWidget *deeperChild = child->childAt(childPos);
        while (deeperChild) {
            child = deeperChild;
            childPos = child->mapFrom(this, eventPos);
            deeperChild = child->childAt(childPos);
        }

        // Create a new tablet event with position relative to the child widget
        QPointF localPosF = child->mapFrom(this, eventPos);
        QTabletEvent childEvent(event->type(),
                                localPosF,
                                event->globalPosF(),
                                event->device(),
                                event->pointerType(),
                                event->pressure(),
                                event->xTilt(),
                                event->yTilt(),
                                event->tangentialPressure(),
                                event->rotation(),
                                event->z(),
                                event->modifiers(),
                                event->uniqueId(),
                                event->button(),
                                event->buttons());

        QApplication::sendEvent(child, &childEvent);

        if (childEvent.isAccepted()) {
            event->accept();
            return;
        }
    }

    // If not handled, ignore to allow normal propagation
    event->ignore();
}

void WGSelectorPopup::replaceCentranWidget(QWidget *widget)
{
    widget->setParent(this);
    while (QLayoutItem *child = layout()->takeAt(0)) {
        delete child->widget();
        delete child;
    }
    layout()->addWidget(widget);
    widget->show();
    layout()->update();
    adjustSize();
}


