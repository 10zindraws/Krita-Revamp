/*
 *  SPDX-FileCopyrightText: 2026 Krita Contributors
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KisTemplateItemDelegate.h"

#include <QPainter>
#include <QApplication>
#include <QStyle>

KisTemplateItemDelegate::KisTemplateItemDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
}

void KisTemplateItemDelegate::paint(QPainter *painter, const QStyleOptionViewItem &option,
                                    const QModelIndex &index) const
{
    painter->save();

    QStyleOptionViewItem opt = option;
    initStyleOption(&opt, index);

    const QWidget *widget = opt.widget;
    QStyle *style = widget ? widget->style() : QApplication::style();

    // Get layout metrics
    const int iconSize = opt.decorationSize.width();
    const int spacing = style->pixelMetric(QStyle::PM_FocusFrameHMargin, &opt, widget) + 1;

    // Calculate icon and text rects
    QRect iconRect = opt.rect;
    iconRect.setWidth(iconSize);
    iconRect.setHeight(iconSize);
    iconRect.moveTop(opt.rect.top() + (opt.rect.height() - iconSize) / 2);
    iconRect.moveLeft(opt.rect.left() + spacing);

    QRect textRect = opt.rect;
    textRect.setLeft(iconRect.right() + spacing * 2);

    // Draw selection highlight only on the text area (not overlapping the icon)
    if (opt.state & QStyle::State_Selected) {
        QRect highlightRect = textRect;
        highlightRect.setRight(opt.rect.right());
        painter->fillRect(highlightRect, opt.palette.highlight());
    }

    // Draw the icon without any selection styling (prevents desaturation)
    QIcon icon = opt.icon;
    if (!icon.isNull()) {
        QIcon::Mode iconMode = QIcon::Normal;
        QIcon::State iconState = (opt.state & QStyle::State_Open) ? QIcon::On : QIcon::Off;
        icon.paint(painter, iconRect, Qt::AlignCenter, iconMode, iconState);
    }

    // Draw the text
    if (!opt.text.isEmpty()) {
        QPalette::ColorGroup cg = (opt.state & QStyle::State_Enabled)
                                      ? QPalette::Normal
                                      : QPalette::Disabled;
        if (cg == QPalette::Normal && !(opt.state & QStyle::State_Active)) {
            cg = QPalette::Inactive;
        }

        QColor textColor;
        if (opt.state & QStyle::State_Selected) {
            textColor = opt.palette.color(cg, QPalette::HighlightedText);
        } else {
            textColor = opt.palette.color(cg, QPalette::Text);
        }

        painter->setPen(textColor);
        painter->drawText(textRect, Qt::AlignLeft | Qt::AlignVCenter, opt.text);
    }

    // Draw focus rect if needed
    if (opt.state & QStyle::State_HasFocus) {
        QStyleOptionFocusRect focusOpt;
        focusOpt.QStyleOption::operator=(opt);
        focusOpt.rect = textRect;
        focusOpt.state |= QStyle::State_KeyboardFocusChange;
        style->drawPrimitive(QStyle::PE_FrameFocusRect, &focusOpt, painter, widget);
    }

    painter->restore();
}
