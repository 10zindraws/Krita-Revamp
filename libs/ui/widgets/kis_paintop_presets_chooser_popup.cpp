/* This file is part of the KDE project
 * SPDX-FileCopyrightText: 2010 Sven Langkamp <sven.langkamp@gmail.com>
 * SPDX-FileCopyrightText: 2011 Srikanth Tiyyagura <srikanth.tulasiram@gmail.com>
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "kis_paintop_presets_chooser_popup.h"

#include <QToolButton>
#include <QCompleter>
#include <QMenu>
#include <QWidgetAction>
#include <QSlider>
#include <QVBoxLayout>
#include <QComboBox>

#include <KoResource.h>
#include <KisResourceItemChooser.h>

#include <ui_wdgpaintoppresets.h>
#include <kis_config.h>
#include <KisResourceServerProvider.h>
#include <brushengine/kis_paintop_preset.h>
#include <kis_icon.h>
#include <brushengine/kis_paintop_settings.h>
#include "KisPopupButton.h"
#include "KisBrushTagSelectorWidget.h"
#include "KisTagChooserWidget.h"
#include "KisResourceTaggingManager.h"
#include <KisTagModel.h>

struct KisPaintOpPresetsChooserPopup::Private
{
public:
    Ui_WdgPaintOpPresets uiWdgPaintOpPresets;
    bool firstShown {true};
    QSlider* iconSizeSlider {nullptr};
    KisPopupButton *viewModeButton {nullptr};
    KisBrushTagSelectorWidget *tagSelectorWidget {nullptr};
};

KisPaintOpPresetsChooserPopup::KisPaintOpPresetsChooserPopup(QWidget * parent)
    : QWidget(parent)
    , m_d(new Private())
{
    m_d->uiWdgPaintOpPresets.setupUi(this);

    // Create and add the tag selector widget at the top
    m_d->tagSelectorWidget = new KisBrushTagSelectorWidget(this);
    QVBoxLayout *mainLayout = qobject_cast<QVBoxLayout *>(layout());
    if (mainLayout) {
        mainLayout->insertWidget(0, m_d->tagSelectorWidget);
    }

    QMenu* menu = new QMenu(this);
    menu->setStyleSheet("margin: 6px");

    menu->addSection(i18nc("@title Which elements to display (e.g., thumbnails or details)", "Display"));

    QActionGroup *actionGroup = new QActionGroup(this);

    KisPresetChooser::ViewMode mode = (KisPresetChooser::ViewMode)KisConfig(true).presetChooserViewMode();

    QAction* action = menu->addAction(KisIconUtils::loadIcon("view-preview"), i18n("Thumbnails"), this, SLOT(slotThumbnailMode()));
    action->setCheckable(true);
    action->setChecked(mode == KisPresetChooser::THUMBNAIL);
    action->setActionGroup(actionGroup);

    action = menu->addAction(KisIconUtils::loadIcon("view-list-details"), i18n("Details"), this, SLOT(slotDetailMode()));
    action->setCheckable(true);
    action->setChecked(mode == KisPresetChooser::DETAIL);
    action->setActionGroup(actionGroup);

    action = menu->addAction(KisIconUtils::loadIcon("krita_tool_freehand"), i18n("Stroke"), this, SLOT(slotStrokeMode()));
    action->setCheckable(true);
    action->setChecked(mode == KisPresetChooser::STROKE);
    action->setActionGroup(actionGroup);

    // add widget slider to control icon size
    QSlider* iconSizeSlider = new QSlider(this);
    iconSizeSlider->setOrientation(Qt::Horizontal);
    iconSizeSlider->setRange(30, 80);
    iconSizeSlider->setValue(m_d->uiWdgPaintOpPresets.wdgPresetChooser->iconSize());
    iconSizeSlider->setMinimumHeight(20);
    iconSizeSlider->setMinimumWidth(40);
    iconSizeSlider->setTickInterval(10);
    m_d->iconSizeSlider = iconSizeSlider;

    QWidgetAction *sliderAction= new QWidgetAction(this);
    sliderAction->setDefaultWidget(iconSizeSlider);

    menu->addSection(i18n("Icon Size"));
    menu->addAction(sliderAction);



    // setting the view mode
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->setViewMode(mode);
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->showTaggingBar(true);

    m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->showViewModeBtn(true);
    m_d->viewModeButton = m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->viewModeButton();
    m_d->viewModeButton->setPopupWidget(menu);

    // Hide the Tag button from the bottom row (replaced by tag selector widget)
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->showTagToolBtn(false);

    // Setup the tag selector widget
    KisTagChooserWidget *tagChooser = m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->tagChooserWidget();
    if (tagChooser) {
        // Get the tag model from the tag chooser's combobox
        KisTagModel *tagModel = qobject_cast<KisTagModel *>(tagChooser->findChild<QComboBox *>()->model());
        if (tagModel) {
            m_d->tagSelectorWidget->setTagModel(tagModel);
        }
        m_d->tagSelectorWidget->setTagChooserWidget(tagChooser);

        // Sync initial selection
        KisTagSP currentTag = tagChooser->currentlySelectedTag();
        if (currentTag) {
            m_d->tagSelectorWidget->setCurrentTag(currentTag);
        }
    }

    connect(m_d->tagSelectorWidget, &KisBrushTagSelectorWidget::sizeHintChanged,
            this, &KisPaintOpPresetsChooserPopup::slotTagSelectorSizeHintChanged);

    connect(m_d->uiWdgPaintOpPresets.wdgPresetChooser, SIGNAL(resourceSelected(KoResourceSP )),
            this, SIGNAL(resourceSelected(KoResourceSP )));
    connect(m_d->uiWdgPaintOpPresets.wdgPresetChooser, SIGNAL(resourceClicked(KoResourceSP )),
            this, SIGNAL(resourceClicked(KoResourceSP ))) ;
    connect(m_d->uiWdgPaintOpPresets.wdgPresetChooser, SIGNAL(resourceDoubleClicked(KoResourceSP )),
            this, SIGNAL(resourceDoubleClicked(KoResourceSP )));


    connect(iconSizeSlider, SIGNAL(valueChanged(int)),
            m_d->uiWdgPaintOpPresets.wdgPresetChooser, SLOT(setIconSize(int)));
    connect(menu, SIGNAL(aboutToHide()),
            m_d->uiWdgPaintOpPresets.wdgPresetChooser, SLOT(saveIconSize()));
    connect(m_d->viewModeButton, SIGNAL(pressed()), this, SLOT(slotUpdateMenu()));

}

KisPaintOpPresetsChooserPopup::~KisPaintOpPresetsChooserPopup()
{
    delete m_d;
}

void KisPaintOpPresetsChooserPopup::slotThumbnailMode()
{
    KisConfig(false).setPresetChooserViewMode(KisPresetChooser::THUMBNAIL);
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->setViewMode(KisPresetChooser::THUMBNAIL);
}

void KisPaintOpPresetsChooserPopup::slotDetailMode()
{
    KisConfig(false).setPresetChooserViewMode(KisPresetChooser::DETAIL);
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->setViewMode(KisPresetChooser::DETAIL);
}

void KisPaintOpPresetsChooserPopup::slotStrokeMode()
{
    KisConfig(false).setPresetChooserViewMode(KisPresetChooser::STROKE);
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->setViewMode(KisPresetChooser::STROKE);
}

void KisPaintOpPresetsChooserPopup::slotUpdateMenu()
{
    QSignalBlocker b(m_d->iconSizeSlider);
    m_d->iconSizeSlider->setValue(KisConfig(true).presetIconSize());
}

void KisPaintOpPresetsChooserPopup::paintEvent(QPaintEvent* event)
{
    QWidget::paintEvent(event);
    //Workaround to get the column and row size right
    if(m_d->firstShown) {
        m_d->uiWdgPaintOpPresets.wdgPresetChooser->updateViewSettings();
        m_d->firstShown = false;
    }
}

void KisPaintOpPresetsChooserPopup::canvasResourceChanged(KisPaintOpPresetSP  preset)
{
    if (preset) {
        blockSignals(true);
        m_d->uiWdgPaintOpPresets.wdgPresetChooser->setCurrentResource(preset);
        blockSignals(false);
    }
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->updateViewSettings();
}

void KisPaintOpPresetsChooserPopup::slotThemeChanged()
{
   m_d->viewModeButton->setIcon(KisIconUtils::loadIcon("view-choose"));
   m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->updateView(); // updates other icons
}

void KisPaintOpPresetsChooserPopup::updateViewSettings()
{
   m_d->uiWdgPaintOpPresets.wdgPresetChooser->updateViewSettings();
}

void KisPaintOpPresetsChooserPopup::setResponsiveness(bool value)
{
    m_d->uiWdgPaintOpPresets.wdgPresetChooser->itemChooser()->setResponsiveness(value);
}

void KisPaintOpPresetsChooserPopup::slotTagSelectorSizeHintChanged()
{
    // When tags are added/removed, the tag selector widget may need more or less rows.
    // This updates the layout to accommodate the new size.
    updateGeometry();
}
