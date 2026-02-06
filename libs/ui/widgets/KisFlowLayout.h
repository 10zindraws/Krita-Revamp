/*
 *  SPDX-FileCopyrightText: 2026 Tenzin Rangdol <tenzindraws@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef KIS_FLOW_LAYOUT_H
#define KIS_FLOW_LAYOUT_H

#include <QLayout>
#include <QRect>
#include <QStyle>
#include <kritaui_export.h>

/**
 * @brief A flow layout that arranges widgets in rows, wrapping to new rows as needed.
 *
 * This layout arranges child widgets horizontally, wrapping to new rows when there
 * isn't enough space. It's useful for displaying a variable number of items (like
 * tag buttons) in a compact space.
 */
class KRITAUI_EXPORT KisFlowLayout : public QLayout
{
    Q_OBJECT

public:
    explicit KisFlowLayout(QWidget *parent = nullptr, int margin = -1, int hSpacing = -1, int vSpacing = -1);
    explicit KisFlowLayout(int margin = -1, int hSpacing = -1, int vSpacing = -1);
    ~KisFlowLayout() override;

    void addItem(QLayoutItem *item) override;
    int horizontalSpacing() const;
    int verticalSpacing() const;
    Qt::Orientations expandingDirections() const override;
    bool hasHeightForWidth() const override;
    int heightForWidth(int width) const override;
    int count() const override;
    QLayoutItem *itemAt(int index) const override;
    QSize minimumSize() const override;
    void setGeometry(const QRect &rect) override;
    QSize sizeHint() const override;
    QLayoutItem *takeAt(int index) override;

private:
    int doLayout(const QRect &rect, bool testOnly) const;
    int smartSpacing(QStyle::PixelMetric pm) const;

    QList<QLayoutItem *> m_itemList;
    int m_hSpace;
    int m_vSpace;
};

#endif // KIS_FLOW_LAYOUT_H
