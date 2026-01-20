/* This file is part of the KDE project
 * SPDX-FileCopyrightText: 2019 Wolthera van Hövell tot Westerflier <griffinvalley@gmail.com>
 * SPDX-FileCopyrightText: 2026 Tenzin Rangdol tenzindraws@gmail.com
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KisResourceItemListView.h"

#include <QEvent>
#include <QScroller>
#include <QScrollBar>
#include <QHelpEvent>
#include <QMouseEvent>
#include <QDrag>
#include <QMimeData>
#include <QPainter>
#include <QApplication>
#include <QDebug>

#include <KisResourceModel.h>

#include "KisIconToolTip.h"

// Visual constants for drag highlighting (matching preset_groups style)
static const QColor HIGHLIGHT_COLOR(70, 170, 255, 255);
static const int LEFT_EDGE_WIDTH = 6;
static const int RIGHT_EDGE_WIDTH = 6;

struct Q_DECL_HIDDEN KisResourceItemListView::Private
{
    ListViewMode viewMode = ListViewMode::IconGrid;
    bool strictSelectionMode {false};
    KisIconToolTip tip;

    QScroller* scroller {0};
    QString prev_scrollbar_style;

    QSize requestedItemSize = QSize(64, 64);

    // Drag-drop state
    bool dragReorderEnabled {false};
    bool isDragging {false};
    bool potentialDrag {false};          // True when we might start a drag
    bool clickedOnSelected {false};      // True if clicked item was already selected
    QPoint dragStartPosition;
    QModelIndex dragStartIndex;
    QModelIndex dropTargetIndex;
    bool dropOnLeftSide {false};
    QTimer *dragHighlightTimer {nullptr};
};

KisResourceItemListView::KisResourceItemListView(QWidget *parent)
    : QListView(parent)
    , m_d(new Private)
{
    setSelectionMode(QAbstractItemView::ExtendedSelection);
    setContextMenuPolicy(Qt::DefaultContextMenu);
    setResizeMode(QListView::Adjust);
    setUniformItemSizes(true);

    // Default configuration
    setViewMode(QListView::IconMode);
    setGridSize(QSize(64, 64));
    setIconSize(QSize(64, 64));

    // Enable drag-drop
    setDragEnabled(false); // We handle drag manually
    setAcceptDrops(true);
    setDropIndicatorShown(false); // We draw our own indicator

    m_d->scroller = KisKineticScroller::createPreconfiguredScroller(this);
    if (m_d->scroller) {
        connect(m_d->scroller, SIGNAL(stateChanged(QScroller::State)), this, SLOT(slotScrollerStateChange(QScroller::State)));
    }

    connect(this, SIGNAL(clicked(QModelIndex)), SIGNAL(currentResourceClicked(const QModelIndex &)));

    m_d->prev_scrollbar_style = horizontalScrollBar()->styleSheet();

    // Timer for smooth drag highlight updates
    m_d->dragHighlightTimer = new QTimer(this);
    m_d->dragHighlightTimer->setInterval(16); // ~60fps
    connect(m_d->dragHighlightTimer, &QTimer::timeout, this, &KisResourceItemListView::updateDragHighlight);
}

KisResourceItemListView::~KisResourceItemListView()
{
}

void KisResourceItemListView::setListViewMode(ListViewMode viewMode)
{
    m_d->viewMode = viewMode;

    auto restoreScrollbar = [&, this] () {
        horizontalScrollBar()->setStyleSheet(m_d->prev_scrollbar_style);
        setVerticalScrollBarPolicy(Qt::ScrollBarPolicy::ScrollBarAsNeeded);
    };

    switch (viewMode) {
    case ListViewMode::IconGrid: {
        setViewMode(ViewMode::IconMode);
        setFlow(Flow::LeftToRight);
        setWrapping(true);
        restoreScrollbar();

        setItemSize(m_d->requestedItemSize);
        break;
    }
    case ListViewMode::IconStripHorizontal: {
        setViewMode(ViewMode::IconMode);
        setFlow(Flow::LeftToRight);
        setWrapping(false);

        // this is the only way to hide it and not have it ocupy space
        horizontalScrollBar()->setStyleSheet("QScrollBar::horizontal {height: 0px;}");
        setVerticalScrollBarPolicy(Qt::ScrollBarPolicy::ScrollBarAlwaysOff);

        setItemSize(m_d->requestedItemSize);
        break;
    }
    case ListViewMode::Detail: {
        setViewMode(ViewMode::ListMode);
        setFlow(Flow::TopToBottom);
        setWrapping(false);
        restoreScrollbar();

        setItemSize(m_d->requestedItemSize);
        break;
    }
    }
}

void KisResourceItemListView::setItemSize(QSize size)
{
    m_d->requestedItemSize = size;

    switch (m_d->viewMode) {
    case ListViewMode::IconGrid: {
        setGridSize(size);
        setIconSize(size);
        break;
    }
    case ListViewMode::IconStripHorizontal: {
        // you can not set the item size in strip mode
        // it is configured automatically based on size
        break;
    }
    case ListViewMode::Detail: {
        const int w = width() - horizontalScrollBar()->width();
        setGridSize(QSize(w, size.height()));
        setIconSize(QSize(size));
        break;
    }
    }
}

void KisResourceItemListView::setStrictSelectionMode(bool enable)
{
    m_d->strictSelectionMode = enable;
    if (enable) {
        setSelectionMode(QAbstractItemView::SingleSelection);
    } else {
        setSelectionMode(QAbstractItemView::ExtendedSelection);
    }
}

void KisResourceItemListView::setDragReorderEnabled(bool enable)
{
    m_d->dragReorderEnabled = enable;
}

bool KisResourceItemListView::isDragReorderEnabled() const
{
    return m_d->dragReorderEnabled;
}

void KisResourceItemListView::setFixedToolTipThumbnailSize(const QSize &size)
{
    m_d->tip.setFixedToolTipThumbnailSize(size);
}

void KisResourceItemListView::setToolTipShouldRenderCheckers(bool value)
{
    m_d->tip.setToolTipShouldRenderCheckers(value);
}

QList<int> KisResourceItemListView::getSelectedResourceIds() const
{
    QList<int> ids;
    QModelIndexList selected = selectionModel()->selectedIndexes();
    for (const QModelIndex &idx : selected) {
        int id = idx.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt();
        if (id > 0) {
            ids.append(id);
        }
    }
    return ids;
}

void KisResourceItemListView::rowsAboutToBeRemoved(const QModelIndex &parent, int start, int end)
{
    // QAbstractItemView moves the current index if the row it points to is removed,
    // which we don't want for strict selections
    QModelIndex current = currentIndex();
    if (selectionMode() == SingleSelection
            && m_d->strictSelectionMode
            && current.isValid()
            && current.row() >= start
            && current.row() <= end) {

        selectionModel()->clear();
    }
    QListView::rowsAboutToBeRemoved(parent, start, end);
}

void KisResourceItemListView::selectionChanged(const QItemSelection &selected, const QItemSelection &deselected)
{
    // base class takes care of viewport updates
    QListView::selectionChanged(selected, deselected);

    if (selected.isEmpty()) {
        Q_EMIT currentResourceChanged(QModelIndex());
    }
    else {
        Q_EMIT currentResourceChanged(selected.indexes().first());
    }
}

QItemSelectionModel::SelectionFlags KisResourceItemListView::selectionCommand(const QModelIndex &index, const QEvent *event) const
{
    QItemSelectionModel::SelectionFlags cmd = QListView::selectionCommand(index, event);

    // avoid deselecting the current item by Ctrl-clicking in single selection mode
    if (selectionMode() == SingleSelection
            && m_d->strictSelectionMode
            && cmd.testFlag(QItemSelectionModel::Deselect)) {

        cmd = QItemSelectionModel::NoUpdate;
    }
    return cmd;
}

void KisResourceItemListView::contextMenuEvent(QContextMenuEvent *event)
{
    QListView::contextMenuEvent(event);
    Q_EMIT contextMenuRequested(event->globalPos());
}

bool KisResourceItemListView::viewportEvent(QEvent *event)
{
    if (!model()) return true;

    if (event->type() == QEvent::ToolTip) {
        QHelpEvent *he = static_cast<QHelpEvent *>(event);
        QStyleOptionViewItem option = viewOptions();
        QModelIndex index = model()->buddy(indexAt(he->pos()));
        if (index.isValid()) {
            option.rect = visualRect(index);
            m_d->tip.showTip(this, he->pos(), option, index);
            return true;
        }
        m_d->tip.hide();
    }

    return QListView::viewportEvent(event);
}

void KisResourceItemListView::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton && m_d->dragReorderEnabled) {
        m_d->dragStartPosition = event->pos();
        m_d->dragStartIndex = indexAt(event->pos());
        m_d->potentialDrag = false;
        m_d->clickedOnSelected = false;

        if (m_d->dragStartIndex.isValid()) {
            // Check if clicked item is already selected
            m_d->clickedOnSelected = selectionModel()->isSelected(m_d->dragStartIndex);

            // If the item is already selected and no modifier keys,
            // we might be starting a drag - don't change selection yet
            if (m_d->clickedOnSelected &&
                !(event->modifiers() & (Qt::ControlModifier | Qt::ShiftModifier))) {
                m_d->potentialDrag = true;
                // Don't call parent - this prevents deselecting other items
                // Use NoUpdate flag to set current index WITHOUT changing selection
                // (setCurrentIndex() would call selectionCommand() which could clear selection)
                selectionModel()->setCurrentIndex(m_d->dragStartIndex, QItemSelectionModel::NoUpdate);
                return;
            }
        }
    }
    QListView::mousePressEvent(event);
}

void KisResourceItemListView::mouseMoveEvent(QMouseEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        QListView::mouseMoveEvent(event);
        return;
    }

    if (!(event->buttons() & Qt::LeftButton)) {
        QListView::mouseMoveEvent(event);
        return;
    }

    if (!m_d->dragStartIndex.isValid()) {
        QListView::mouseMoveEvent(event);
        return;
    }

    // Check if we've moved far enough to start a drag
    int distance = (event->pos() - m_d->dragStartPosition).manhattanLength();
    if (distance < QApplication::startDragDistance()) {
        // Don't call parent if we're in potential drag mode
        // This prevents rubber band selection from starting
        if (!m_d->potentialDrag) {
            QListView::mouseMoveEvent(event);
        }
        return;
    }

    // Start drag - don't call parent's mouseMoveEvent to prevent rubber band
    if (!m_d->isDragging) {
        startDrag();
    }
    // Note: We explicitly don't call QListView::mouseMoveEvent here
    // to prevent rubber band selection interference
}

void KisResourceItemListView::mouseReleaseEvent(QMouseEvent *event)
{
    bool wasDragging = m_d->isDragging;
    bool wasPotentialDrag = m_d->potentialDrag;
    QModelIndex clickedIndex = m_d->dragStartIndex;

    if (m_d->isDragging) {
        stopDrag();
    }

    // Reset drag state
    m_d->dragStartIndex = QModelIndex();
    m_d->potentialDrag = false;

    // If we were in potential drag mode but didn't actually drag,
    // now apply the single selection (click on already-selected item)
    if (wasPotentialDrag && !wasDragging && clickedIndex.isValid()) {
        if (event->button() == Qt::LeftButton &&
            !(event->modifiers() & (Qt::ControlModifier | Qt::ShiftModifier))) {
            // Single click on selected item without drag = select only this item
            selectionModel()->select(clickedIndex,
                QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Current);
        }
        // Don't call parent - we've handled the release ourselves
        return;
    }

    QListView::mouseReleaseEvent(event);
}

void KisResourceItemListView::startDrag()
{
    m_d->isDragging = true;
    m_d->potentialDrag = false;  // We're now actually dragging
    m_d->dragHighlightTimer->start();

    // Get selected items for drag
    QList<int> resourceIds = getSelectedResourceIds();

    // Ensure the drag start item is included
    if (m_d->dragStartIndex.isValid()) {
        int dragStartId = m_d->dragStartIndex.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt();
        if (dragStartId > 0 && !resourceIds.contains(dragStartId)) {
            // Item under cursor wasn't selected - select it and use only it
            selectionModel()->select(m_d->dragStartIndex,
                QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Current);
            resourceIds.clear();
            resourceIds.append(dragStartId);
        }
    }

    if (resourceIds.isEmpty()) {
        stopDrag();
        return;
    }

    // Create mime data
    QMimeData *mimeData = new QMimeData();
    QStringList idStrings;
    for (int id : resourceIds) {
        idStrings.append(QString::number(id));
    }
    mimeData->setData("application/x-krita-resourceids", idStrings.join(",").toUtf8());

    // Create drag object
    QDrag *drag = new QDrag(this);
    drag->setMimeData(mimeData);

    // Set drag pixmap from first selected item
    QPixmap pixmap = m_d->dragStartIndex.data(Qt::DecorationRole).value<QIcon>().pixmap(32, 32);
    if (!pixmap.isNull()) {
        drag->setPixmap(pixmap);
        drag->setHotSpot(QPoint(16, 16));
    }

    // Execute drag - this blocks until drop or cancel
    drag->exec(Qt::MoveAction);

    stopDrag();
}

void KisResourceItemListView::stopDrag()
{
    m_d->isDragging = false;
    m_d->potentialDrag = false;
    m_d->clickedOnSelected = false;
    m_d->dragHighlightTimer->stop();
    m_d->dropTargetIndex = QModelIndex();
    viewport()->update();
}

void KisResourceItemListView::dragEnterEvent(QDragEnterEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->acceptProposedAction();
    } else {
        event->ignore();
    }
}

void KisResourceItemListView::dragMoveEvent(QDragMoveEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (!event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->ignore();
        return;
    }

    event->acceptProposedAction();

    // Update drop target for visual feedback
    QModelIndex idx = indexAt(event->pos());
    if (idx.isValid()) {
        m_d->dropTargetIndex = idx;
        m_d->dropOnLeftSide = isLeftHalf(event->pos(), idx);
    } else {
        // Dropped on empty area - append to end
        m_d->dropTargetIndex = QModelIndex();
    }

    viewport()->update();
}

void KisResourceItemListView::dragLeaveEvent(QDragLeaveEvent *event)
{
    Q_UNUSED(event);
    m_d->dropTargetIndex = QModelIndex();
    viewport()->update();
}

void KisResourceItemListView::dropEvent(QDropEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (!event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->ignore();
        return;
    }

    event->acceptProposedAction();

    // Parse resource IDs from mime data
    QByteArray data = event->mimeData()->data("application/x-krita-resourceids");
    QStringList idStrings = QString::fromUtf8(data).split(",");
    QList<int> resourceIds;
    for (const QString &str : idStrings) {
        bool ok;
        int id = str.toInt(&ok);
        if (ok && id > 0) {
            resourceIds.append(id);
        }
    }

    if (resourceIds.isEmpty()) {
        return;
    }

    // Calculate drop position
    int targetPosition = calculateDropPosition(event->pos());

    // Emit signal for the chooser to handle the reorder
    Q_EMIT resourcesReordered(resourceIds, targetPosition);

    // Clear drop target
    m_d->dropTargetIndex = QModelIndex();
    viewport()->update();
}

int KisResourceItemListView::calculateDropPosition(const QPoint &pos) const
{
    QModelIndex idx = indexAt(pos);
    if (!idx.isValid()) {
        // Dropped on empty area - append to end
        return model() ? model()->rowCount() : 0;
    }

    int row = idx.row();
    if (!isLeftHalf(pos, idx)) {
        // Drop on right/bottom side means insert after this item
        row++;
    }
    return row;
}

bool KisResourceItemListView::isLeftHalf(const QPoint &pos, const QModelIndex &index) const
{
    QRect rect = visualRect(index);
    if (!rect.isValid()) return true;

    // In Detail mode (list view), use top/bottom split instead of left/right
    if (m_d->viewMode == ListViewMode::Detail) {
        // 50/50 split vertically
        int midY = rect.top() + rect.height() / 2;
        return pos.y() < midY;
    }

    // For icon modes, use left/right split
    // 50/50 split horizontally
    int midX = rect.left() + rect.width() / 2;
    return pos.x() < midX;
}

void KisResourceItemListView::paintEvent(QPaintEvent *event)
{
    QListView::paintEvent(event);

    // Draw drop indicator if we have a valid drop target
    if (m_d->dropTargetIndex.isValid() && m_d->isDragging) {
        QPainter painter(viewport());
        drawDropIndicator(&painter, m_d->dropTargetIndex, m_d->dropOnLeftSide);
    }
}

void KisResourceItemListView::drawDropIndicator(QPainter *painter, const QModelIndex &index, bool leftSide)
{
    QRect rect = visualRect(index);
    if (!rect.isValid()) return;

    painter->save();
    painter->setRenderHint(QPainter::Antialiasing, true);

    QPen pen(HIGHLIGHT_COLOR);
    pen.setWidth(leftSide ? LEFT_EDGE_WIDTH : RIGHT_EDGE_WIDTH);
    painter->setPen(pen);
    painter->setBrush(Qt::NoBrush);

    // In Detail mode (list view), draw horizontal lines (top/bottom)
    if (m_d->viewMode == ListViewMode::Detail) {
        int y = leftSide ? rect.top() + LEFT_EDGE_WIDTH / 2 : rect.bottom() - RIGHT_EDGE_WIDTH / 2;
        painter->drawLine(rect.left(), y, rect.right(), y);
    } else {
        // For icon modes, draw vertical lines (left/right)
        int x = leftSide ? rect.left() + LEFT_EDGE_WIDTH / 2 : rect.right() - RIGHT_EDGE_WIDTH / 2;
        painter->drawLine(x, rect.top(), x, rect.bottom());
    }

    painter->restore();
}

void KisResourceItemListView::updateDragHighlight()
{
    // This is called during drag to update the visual highlight
    // The actual update is done in dragMoveEvent, this just ensures smooth updates
    if (m_d->isDragging) {
        viewport()->update();
    }
}

void KisResourceItemListView::resizeEvent(QResizeEvent *event)
{
    QListView::resizeEvent(event);

    switch (m_d->viewMode) {
    case ListViewMode::IconStripHorizontal: {
        const int height = event->size().height();
        setGridSize(QSize(height, height));
        setIconSize(QSize(height, height));
        break;
    }
    case ListViewMode::Detail: {
        setItemSize(m_d->requestedItemSize);
    }
    }
    scrollTo(currentIndex(), QAbstractItemView::PositionAtCenter);
}
