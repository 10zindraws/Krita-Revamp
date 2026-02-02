/*
 *  SPDX-FileCopyrightText: 2026 Krita Contributors
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

#ifndef KIS_TEMPLATE_ITEM_DELEGATE_H
#define KIS_TEMPLATE_ITEM_DELEGATE_H

#include <QStyledItemDelegate>

/**
 * @brief Custom item delegate for template list items
 *
 * This delegate draws the selection highlight without overlapping the icon,
 * preventing the thumbnail from becoming desaturated when selected.
 */
class KisTemplateItemDelegate : public QStyledItemDelegate
{
    Q_OBJECT

public:
    explicit KisTemplateItemDelegate(QObject *parent = nullptr);

    void paint(QPainter *painter, const QStyleOptionViewItem &option,
               const QModelIndex &index) const override;
};

#endif // KIS_TEMPLATE_ITEM_DELEGATE_H
