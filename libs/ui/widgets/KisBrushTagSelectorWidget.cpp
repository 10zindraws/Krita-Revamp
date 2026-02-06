/*
 *  SPDX-FileCopyrightText: 2026 Tenzin Rangdol <tenzindraws@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "KisBrushTagSelectorWidget.h"

#include <QContextMenuEvent>
#include <QMenu>
#include <QVBoxLayout>

#include <klocalizedstring.h>
#include <KoIcon.h>

#include <KisTagModel.h>
#include "KisFlowLayout.h"
#include "KisTagChooserWidget.h"
#include "TagActions.h"
#include "KisMenuStyleDontCloseOnAlt.h"

KisBrushTagSelectorWidget::KisBrushTagSelectorWidget(QWidget *parent)
    : QWidget(parent)
    , m_flowLayout(new KisFlowLayout(this, 2, 3, 3))
    , m_buttonGroup(new QButtonGroup(this))
    , m_tagModel(nullptr)
    , m_tagChooser(nullptr)
    , m_isUpdating(false)
{
    m_buttonGroup->setExclusive(true);
    connect(m_buttonGroup, QOverload<QAbstractButton *>::of(&QButtonGroup::buttonClicked),
            this, &KisBrushTagSelectorWidget::onButtonClicked);

    setLayout(m_flowLayout);
    setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Minimum);
}

KisBrushTagSelectorWidget::~KisBrushTagSelectorWidget()
{
    clearButtons();
}

void KisBrushTagSelectorWidget::setTagModel(KisTagModel *model)
{
    if (m_tagModel) {
        disconnect(m_tagModel, nullptr, this, nullptr);
    }

    m_tagModel = model;

    if (m_tagModel) {
        connect(m_tagModel, &QAbstractItemModel::rowsInserted,
                this, &KisBrushTagSelectorWidget::onModelRowsInserted);
        connect(m_tagModel, &QAbstractItemModel::rowsRemoved,
                this, &KisBrushTagSelectorWidget::onModelRowsRemoved);
        connect(m_tagModel, &QAbstractItemModel::modelReset,
                this, &KisBrushTagSelectorWidget::onModelReset);
        connect(m_tagModel, &QAbstractItemModel::dataChanged,
                this, &KisBrushTagSelectorWidget::rebuildButtons);

        rebuildButtons();
    }
}

void KisBrushTagSelectorWidget::setTagChooserWidget(KisTagChooserWidget *tagChooser)
{
    if (m_tagChooser) {
        disconnect(m_tagChooser, nullptr, this, nullptr);
    }

    m_tagChooser = tagChooser;

    if (m_tagChooser) {
        connect(m_tagChooser, &KisTagChooserWidget::sigTagChosen,
                this, &KisBrushTagSelectorWidget::setCurrentTag);
    }
}

KisTagSP KisBrushTagSelectorWidget::currentTag() const
{
    return m_currentTag;
}

void KisBrushTagSelectorWidget::setCurrentTag(KisTagSP tag)
{
    if (m_isUpdating) {
        return;
    }

    m_currentTag = tag;
    syncButtonSelection();
}

void KisBrushTagSelectorWidget::onButtonClicked(QAbstractButton *button)
{
    if (m_isUpdating || !m_tagModel) {
        return;
    }

    int index = m_buttons.indexOf(static_cast<QPushButton *>(button));
    if (index < 0 || index >= m_tagModel->rowCount()) {
        return;
    }

    QModelIndex modelIndex = m_tagModel->index(index, 0);
    KisTagSP tag = m_tagModel->tagForIndex(modelIndex);

    if (tag && tag != m_currentTag) {
        m_isUpdating = true;
        m_currentTag = tag;

        // Sync with tag chooser combobox
        if (m_tagChooser) {
            m_tagChooser->setCurrentItem(tag->url());
        }

        Q_EMIT tagSelected(tag);
        m_isUpdating = false;
    }
}

void KisBrushTagSelectorWidget::rebuildButtons()
{
    if (!m_tagModel) {
        return;
    }

    m_isUpdating = true;

    // Store current size hint before changes
    QSize oldHint = sizeHint();

    clearButtons();

    for (int i = 0; i < m_tagModel->rowCount(); ++i) {
        QModelIndex index = m_tagModel->index(i, 0);
        KisTagSP tag = m_tagModel->tagForIndex(index);
        if (tag) {
            createButton(tag);
        }
    }

    syncButtonSelection();

    m_isUpdating = false;

    // Check if size hint changed and emit signal
    if (sizeHint() != oldHint) {
        updateGeometry();
        Q_EMIT sizeHintChanged();
    }
}

void KisBrushTagSelectorWidget::onModelRowsInserted(const QModelIndex &parent, int first, int last)
{
    Q_UNUSED(parent);
    Q_UNUSED(first);
    Q_UNUSED(last);
    rebuildButtons();
}

void KisBrushTagSelectorWidget::onModelRowsRemoved(const QModelIndex &parent, int first, int last)
{
    Q_UNUSED(parent);
    Q_UNUSED(first);
    Q_UNUSED(last);
    rebuildButtons();
}

void KisBrushTagSelectorWidget::onModelReset()
{
    rebuildButtons();
}

void KisBrushTagSelectorWidget::clearButtons()
{
    for (QPushButton *btn : qAsConst(m_buttons)) {
        m_buttonGroup->removeButton(btn);
        m_flowLayout->removeWidget(btn);
        btn->deleteLater();
    }
    m_buttons.clear();
}

void KisBrushTagSelectorWidget::createButton(KisTagSP tag)
{
    QPushButton *btn = new QPushButton(tag->name(), this);
    btn->setCheckable(true);
    btn->setProperty("tagUrl", tag->url());
    btn->setContextMenuPolicy(Qt::DefaultContextMenu);

    m_buttonGroup->addButton(btn);
    m_flowLayout->addWidget(btn);
    m_buttons.append(btn);
}

void KisBrushTagSelectorWidget::syncButtonSelection()
{
    if (!m_currentTag) {
        return;
    }

    for (QPushButton *btn : qAsConst(m_buttons)) {
        QString tagUrl = btn->property("tagUrl").toString();
        bool shouldBeChecked = (tagUrl == m_currentTag->url());
        if (btn->isChecked() != shouldBeChecked) {
            btn->setChecked(shouldBeChecked);
        }
    }
}

void KisBrushTagSelectorWidget::contextMenuEvent(QContextMenuEvent *event)
{
    if (!m_tagChooser) {
        QWidget::contextMenuEvent(event);
        return;
    }

    // Find which button was right-clicked
    QPushButton *clickedButton = nullptr;
    for (QPushButton *btn : qAsConst(m_buttons)) {
        if (btn->geometry().contains(event->pos())) {
            clickedButton = btn;
            break;
        }
    }

    if (!clickedButton || !m_tagModel) {
        QWidget::contextMenuEvent(event);
        return;
    }

    // Get the tag for this button
    QString tagUrl = clickedButton->property("tagUrl").toString();
    KisTagSP tag = m_tagModel->tagForUrl(tagUrl);

    if (!tag) {
        QWidget::contextMenuEvent(event);
        return;
    }

    // First, select this tag
    m_isUpdating = true;
    clickedButton->setChecked(true);
    m_currentTag = tag;
    if (m_tagChooser) {
        m_tagChooser->setCurrentItem(tag->url());
    }
    Q_EMIT tagSelected(tag);
    m_isUpdating = false;

    // Create context menu similar to KisTagToolButton
    QMenu *menu = new QMenu(this);

    KisMenuStyleDontCloseOnAlt *menuStyle = new KisMenuStyleDontCloseOnAlt(menu->style());
    menuStyle->setParent(menu);
    menu->setStyle(menuStyle);

    // Add "New tag" action
    UserInputTagAction *addTagAction = new UserInputTagAction(menu);
    addTagAction->setPlaceholderText(i18n("New tag"));
    addTagAction->setIcon(koIcon("document-new"));
    addTagAction->setCloseParentOnTrigger(true);
    menu->addAction(addTagAction);

    connect(addTagAction, &UserInputTagAction::triggered, m_tagChooser,
            QOverload<const QString &>::of(&KisTagChooserWidget::addTag));

    // Check if tag is editable (not a built-in tag)
    bool isReadOnly = tag->id() < 0 || tag->url() == KisAllTagsModel::urlFavorites();

    if (!isReadOnly) {
        // Add "Rename tag" action
        UserInputTagAction *renameTagAction = new UserInputTagAction(menu);
        renameTagAction->setPlaceholderText(i18n("Rename tag"));
        renameTagAction->setIcon(koIcon("edit-rename"));
        renameTagAction->setCloseParentOnTrigger(true);
        menu->addAction(renameTagAction);

        connect(renameTagAction, &UserInputTagAction::triggered, this, [this](const QString &newName) {
            if (m_tagChooser && m_currentTag) {
                // We need to use the tag chooser's internal rename mechanism
                // Since we've selected this tag, the tag chooser will rename the current tag
                QMetaObject::invokeMethod(m_tagChooser, "tagToolRenameCurrentTag",
                                          Qt::DirectConnection, Q_ARG(QString, newName));
            }
        });

        menu->addSeparator();

        // Add "Delete tag" action
        QAction *deleteTagAction = new QAction(menu);
        deleteTagAction->setText(i18n("Delete this tag"));
        deleteTagAction->setIcon(koIcon("edit-delete"));
        menu->addAction(deleteTagAction);

        connect(deleteTagAction, &QAction::triggered, this, [this]() {
            if (m_tagChooser) {
                QMetaObject::invokeMethod(m_tagChooser, "tagToolDeleteCurrentTag",
                                          Qt::DirectConnection);
            }
        });
    }

    menu->exec(event->globalPos());
    delete menu;
}

bool KisBrushTagSelectorWidget::event(QEvent *event)
{
    if (event->type() == QEvent::LayoutRequest) {
        checkSizeHintChanged();
    }
    return QWidget::event(event);
}

QSize KisBrushTagSelectorWidget::previousSizeHint() const
{
    return m_previousSizeHint;
}

void KisBrushTagSelectorWidget::checkSizeHintChanged()
{
    QSize newHint = sizeHint();
    if (newHint != m_previousSizeHint) {
        m_previousSizeHint = newHint;
        Q_EMIT sizeHintChanged();
    }
}
