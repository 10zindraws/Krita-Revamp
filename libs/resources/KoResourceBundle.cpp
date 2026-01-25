/*
 *  SPDX-FileCopyrightText: 2014 Victor Lafon metabolic.ewilan @hotmail.fr
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KoResourceBundle.h"

#include <QBuffer>
#include <QByteArray>
#include <QCryptographicHash>
#include <QDate>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QMessageBox>
#include <QPainter>
#include <QProcessEnvironment>
#include <QScopedPointer>
#include <QSaveFile>
#include <QSet>
#include <QStringList>

#include <klocalizedstring.h>

#include <KisMimeDatabase.h>
#include "KoResourceBundleManifest.h"
#include <KoMD5Generator.h>
#include <KoResourcePaths.h>
#include <KoStore.h>
#include <KoXmlWriter.h>
#include "KisStoragePlugin.h"
#include "KisResourceLoaderRegistry.h"
#include <KisResourceModelProvider.h>
#include <KisResourceModel.h>
#include <KoMD5Generator.h>

#include <KritaVersionWrapper.h>

#include <kis_debug.h>
#include <KisGlobalResourcesInterface.h>


namespace {
QString ensureTrailingSlash(const QString &prefix)
{
    if (prefix.isEmpty() || prefix.endsWith('/')) {
        return prefix;
    }
    return prefix + '/';
}

QString prefixedPath(const QString &prefix, const QString &path)
{
    if (prefix.isEmpty()) {
        return path;
    }
    if (path.isEmpty()) {
        return prefix;
    }
    return prefix + path;
}

QString manifestOverridePath(const QString &bundleFilename)
{
    return QDir::cleanPath(bundleFilename + "_modified/META-INF/manifest.xml");
}

QString normalizedCaseKey(const QString &path)
{
    return QDir::fromNativeSeparators(path).toLower();
}

QString normalizedLooseKey(const QString &path)
{
    QString normalized = normalizedCaseKey(path);
    normalized.replace('_', ' ');
    normalized = normalized.simplified();
    normalized.replace(' ', '_');
    return normalized;
}

QString normalizeMd5String(const QString &md5sum)
{
    if (md5sum.isEmpty()) {
        return md5sum;
    }

    bool isHex = true;
    for (const QChar &ch : md5sum) {
        const QChar lower = ch.toLower();
        if (!lower.isDigit() && (lower < 'a' || lower > 'f')) {
            isHex = false;
            break;
        }
    }

    if (isHex) {
        return md5sum.toLower();
    }

    return QString::fromLatin1(md5sum.toLatin1().toHex());
}

QString resolveMissingPath(const QString &resourcePath, const QStringList &relativeEntries)
{
    QString target = normalizedCaseKey(resourcePath);
    QString resolved;
    int matches = 0;

    for (const QString &entry : relativeEntries) {
        if (normalizedCaseKey(entry) == target) {
            resolved = entry;
            if (++matches > 1) {
                break;
            }
        }
    }

    if (matches == 1) {
        return resolved;
    }

    target = normalizedLooseKey(resourcePath);
    resolved.clear();
    matches = 0;

    for (const QString &entry : relativeEntries) {
        if (normalizedLooseKey(entry) == target) {
            resolved = entry;
            if (++matches > 1) {
                break;
            }
        }
    }

    return matches == 1 ? resolved : QString();
}

QString detectRootPrefix(KoStore *store)
{
    if (!store) {
        return QString();
    }

    if (store->hasFile("META-INF/manifest.xml")) {
        return QString();
    }

    const QStringList entries = store->directoryList();
    const QString manifestSuffix = "META-INF/manifest.xml";
    QString manifestPrefix;

    for (const QString &entry : entries) {
        const QString normalized = QDir::fromNativeSeparators(entry);
        if (normalized.endsWith(manifestSuffix)) {
            QString candidate = normalized.left(normalized.length() - manifestSuffix.length());
            candidate = ensureTrailingSlash(candidate);
            if (manifestPrefix.isEmpty()) {
                manifestPrefix = candidate;
            } else if (manifestPrefix != candidate) {
                manifestPrefix.clear();
                break;
            }
        }
    }

    if (!manifestPrefix.isEmpty()) {
        return manifestPrefix;
    }

    QString topLevel;
    for (const QString &entry : entries) {
        QString normalized = QDir::fromNativeSeparators(entry);
        if (normalized.endsWith('/')) {
            continue;
        }
        int slashIdx = normalized.indexOf('/');
        if (slashIdx <= 0) {
            topLevel.clear();
            break;
        }
        const QString current = normalized.left(slashIdx);
        if (topLevel.isEmpty()) {
            topLevel = current;
        } else if (topLevel != current) {
            topLevel.clear();
            break;
        }
    }

    if (!topLevel.isEmpty()) {
        return ensureTrailingSlash(topLevel);
    }

    return QString();
}
} // namespace


KoResourceBundle::KoResourceBundle(QString const& fileName)
    : m_filename(fileName),
      m_bundleVersion("1")
{
    m_metadata[KisResourceStorage::s_meta_generator] = "Krita (" + KritaVersionWrapper::versionString(true) + ")";
}

KoResourceBundle::~KoResourceBundle()
{
}

QString KoResourceBundle::defaultFileExtension() const
{
    return QString(".bundle");
}

bool KoResourceBundle::load()
{
    if (m_filename.isEmpty()) return false;
    QScopedPointer<KoStore> resourceStore(KoStore::createStore(m_filename, KoStore::Read, "application/x-krita-resourcebundle", KoStore::Zip));

    if (!resourceStore || resourceStore->bad()) {
        qWarning() << "Could not open store on bundle" << m_filename;
        return false;

    }
    else {

        m_metadata.clear();
        m_manifestDirty = false;
        m_manifestOverrideLoaded = false;
        m_rootPrefix = ensureTrailingSlash(detectRootPrefix(resourceStore.data()));

        bool manifestLoaded = false;
        const QString overridePath = manifestOverridePath();
        const QFileInfo overrideInfo(overridePath);
        const QFileInfo bundleInfo(m_filename);

        if (overrideInfo.exists() &&
            (!bundleInfo.exists() || overrideInfo.lastModified() >= bundleInfo.lastModified())) {
            QFile overrideFile(overridePath);
            if (overrideFile.open(QIODevice::ReadOnly)) {
                if (m_manifest.load(&overrideFile)) {
                    manifestLoaded = true;
                    m_manifestOverrideLoaded = true;
                } else {
                    qWarning() << "Could not open manifest override for bundle" << m_filename;
                }
            }
        }

        auto generateManifestFromStore = [&]() -> bool {
            const QStringList resourceTypes = KisResourceLoaderRegistry::instance()->resourceTypes();
#if QT_VERSION >= QT_VERSION_CHECK(5,14,0)
            const QSet<QString> resourceTypeSet(resourceTypes.begin(), resourceTypes.end());
#else
            const QSet<QString> resourceTypeSet = QSet<QString>::fromList(resourceTypes);
#endif
            m_manifest = KoResourceBundleManifest();

            bool foundResources = false;
            const QStringList entries = resourceStore->directoryList();

            for (const QString &entry : entries) {
                QString normalized = QDir::fromNativeSeparators(entry);
                if (normalized.endsWith('/')) {
                    continue;
                }

                QString relative = normalized;
                if (!m_rootPrefix.isEmpty()) {
                    if (!relative.startsWith(m_rootPrefix)) {
                        continue;
                    }
                    relative = relative.mid(m_rootPrefix.length());
                }

                int slashIdx = relative.indexOf('/');
                if (slashIdx <= 0) {
                    continue;
                }

                const QString folder = relative.left(slashIdx);
                if (!resourceTypeSet.contains(folder)) {
                    continue;
                }

                const QString filenameInBundle = relative.mid(folder.length() + 1);
                if (filenameInBundle.isEmpty()) {
                    continue;
                }

                if (!resourceStore->open(normalized)) {
                    continue;
                }
                const QString md5 = KoMD5Generator::generateHash(resourceStore->device());
                resourceStore->close();

                m_manifest.addResource(folder, relative, {}, md5, -1, filenameInBundle);
                foundResources = true;
            }

            if (foundResources) {
                qWarning() << "Bundle" << m_filename << "has no manifest; generated a temporary manifest.";
            }

            return foundResources;
        };

        if (!manifestLoaded) {
            const QString manifestPath = prefixedPath(m_rootPrefix, "META-INF/manifest.xml");
            if (resourceStore->open(manifestPath)) {
                if (!m_manifest.load(resourceStore->device())) {
                    qWarning() << "Could not open manifest for bundle" << m_filename;
                    return false;
                }
                resourceStore->close();
                manifestLoaded = true;
            } else {
                if (!generateManifestFromStore()) {
                    qWarning() << "Could not load META-INF/manifest.xml";
                    return false;
                }
                manifestLoaded = true;
                m_manifestDirty = true;
            }
        }

        QStringList relativeEntries;
        const QStringList storeEntries = resourceStore->directoryList();
        relativeEntries.reserve(storeEntries.size());

        for (const QString &entry : storeEntries) {
            QString normalized = QDir::fromNativeSeparators(entry);
            if (normalized.endsWith('/')) {
                continue;
            }
            if (!m_rootPrefix.isEmpty()) {
                if (!normalized.startsWith(m_rootPrefix)) {
                    continue;
                }
                normalized = normalized.mid(m_rootPrefix.length());
            }
            relativeEntries << normalized;
        }

        QStringList missingFiles;
        Q_FOREACH (KoResourceBundleManifest::ResourceReference ref, m_manifest.files()) {
            if (ref.fileTypeName == "application/x-krita-resourcebundle" || ref.resourcePath == "/") {
                continue;
            }

            const QString resourcePath = ref.resourcePath;
            if (!resourceStore->hasFile(prefixedPath(m_rootPrefix, resourcePath))) {
                const QString resolved = resolveMissingPath(resourcePath, relativeEntries);
                if (!resolved.isEmpty()) {
                    QString filenameInBundle = resolved;
                    if (filenameInBundle.startsWith(ref.fileTypeName + "/")) {
                        filenameInBundle = filenameInBundle.mid(ref.fileTypeName.length() + 1);
                    }
                    m_manifest.removeResource(ref);
                    m_manifest.addResource(ref.fileTypeName, resolved, ref.tagList, ref.md5sum, ref.resourceId, filenameInBundle);
                } else {
                    m_manifest.removeResource(ref);
                    missingFiles << resourcePath;
                }
                m_manifestDirty = true;
            }
        }

        if (!missingFiles.isEmpty()) {
            if (missingFiles.size() <= 3) {
                qWarning() << "Bundle" << filename() << "is broken. Missing files:" << missingFiles.join(", ");
            } else {
                qWarning() << "Bundle" << filename() << "is broken. Missing" << missingFiles.size()
                           << "files, including:" << missingFiles.mid(0, 3).join(", ") << "...";
            }
        }

        if (m_manifestDirty) {
            saveManifestOverride();
        }

        bool versionFound = false;
        if (!readMetaData(resourceStore.data())) {
            qWarning() << "Could not load meta.xml";
            m_metadata[KisResourceStorage::s_meta_generator] =
                "Krita (" + KritaVersionWrapper::versionString(true) + ")";
        }

        if (resourceStore->open(prefixedPath(m_rootPrefix, "preview.png"))) {
            // Workaround for some OS (Debian, Ubuntu), where loading directly from the QIODevice
            // fails with "libpng error: IDAT: CRC error"
            QByteArray data = resourceStore->device()->readAll();
            QBuffer buffer(&data);
            m_thumbnail.load(&buffer, "PNG");
            resourceStore->close();
        }
        else {
            qWarning() << "Could not open preview.png";
        }

        /*
         * If no version is found it's an old bundle with md5 hashes to fix, or if some manifest resource entry
         * doesn't not correspond to a file the bundle is "broken", in both cases we need to recreate the bundle.
         */
        if (!versionFound) {
            m_metadata.insert(KisResourceStorage::s_meta_version, "1");
        }

    }

    return true;
}

bool KoResourceBundle::loadFromDevice(QIODevice *)
{
    return false;
}

bool saveResourceToStore(const QString &filename, KoResourceSP resource, KoStore *store, const QString &resType, KisResourceModel &model)
{
    if (!resource) {
        qWarning() << "No Resource";
        return false;
    }

    if (!resource->valid()) {
        qWarning() << "Resource is not valid";
        return false;
    }
    if (!store || store->bad()) {
        qWarning() << "No Store or Store is Bad";
        return false;
    }

    QBuffer buf;
    buf.open(QFile::WriteOnly);

    bool response = model.exportResource(resource, &buf);
    if (!response) {
        qWarning() << "Cannot save to device";
        return false;
    }

    if (!store->open(resType + "/" + filename)) {
        qWarning() << "Could not open file in store for resource";
        return false;
    }

    qint64 size = store->write(buf.data());
    store->close();
    buf.close();
    if (size != buf.size()) {
        qWarning() << "Cannot save resource to the store" << size << buf.size();
        return false;
    }

    if (!resource->thumbnailPath().isEmpty()) {
        // hack for MyPaint brush presets previews
        const QImage thumbnail = resource->thumbnail();

        // clone resource to find out the file path for its preview
        KoResourceSP clonedResource = resource->clone();
        clonedResource->setFilename(filename);

        if (!store->open(resType + "/" + clonedResource->thumbnailPath())) {
            qWarning() << "Could not open file in store for resource thumbnail";
            return false;
        }
        QBuffer buf;
        buf.open(QFile::ReadWrite);
        thumbnail.save(&buf, "PNG");

        int size2 = store->write(buf.data());
        if (size2 != buf.size()) {
            qWarning() << "Cannot save thumbnail to the store" << size << buf.size();
        }
        store->close();
        buf.close();
    }


    return size == buf.size();
}

bool KoResourceBundle::save()
{
    if (m_filename.isEmpty()) return false;

    if (metaData(KisResourceStorage::s_meta_creation_date, "").isEmpty()) {
        setMetaData(KisResourceStorage::s_meta_creation_date, QLocale::c().toString(QDate::currentDate(), QStringLiteral("dd/MM/yyyy")));
    }
    setMetaData(KisResourceStorage::s_meta_dc_date, QLocale::c().toString(QDate::currentDate(), QStringLiteral("dd/MM/yyyy")));

    QDir bundleDir = KoResourcePaths::saveLocation("data", "bundles");
    bundleDir.cdUp();

    QScopedPointer<KoStore> store(KoStore::createStore(m_filename, KoStore::Write, "application/x-krita-resourcebundle", KoStore::Zip));

    if (!store || store->bad()) return false;

    Q_FOREACH (const QString &resType, m_manifest.types()) {
        KisResourceModel model(resType);
        model.setResourceFilter(KisResourceModel::ShowAllResources);
        Q_FOREACH (const KoResourceBundleManifest::ResourceReference &ref, m_manifest.files(resType)) {
            KoResourceSP res;
            if (ref.resourceId >= 0) res = model.resourceForId(ref.resourceId);
            if (!res) res = model.resourcesForMD5(ref.md5sum).first();
            if (!res) res = model.resourcesForFilename(QFileInfo(ref.resourcePath).fileName()).first();
            if (!res) {
                qWarning() << "Could not find resource" << resType << ref.resourceId << ref.md5sum << ref.resourcePath;
                continue;
            }

            if (!saveResourceToStore(ref.filenameInBundle, res, store.data(), resType, model)) {
                qWarning() << "Could not save resource" << resType << res->name();
            }
        }
    }

    if (!m_thumbnail.isNull()) {
        QByteArray byteArray;
        QBuffer buffer(&byteArray);
        m_thumbnail.save(&buffer, "PNG");
        if (!store->open("preview.png")) qWarning() << "Could not open preview.png";
        if (store->write(byteArray) != buffer.size()) qWarning() << "Could not write preview.png";
        store->close();
    }

    saveManifest(store);

    saveMetadata(store);

    store->finalize();

    return true;
}

bool KoResourceBundle::saveToDevice(QIODevice */*dev*/) const
{
    return false;
}

void KoResourceBundle::setMetaData(const QString &key, const QString &value)
{
    m_metadata.insert(key, value);
}

const QString KoResourceBundle::metaData(const QString &key, const QString &defaultValue) const
{
    if (m_metadata.contains(key)) {
        return m_metadata[key];
    }
    else {
        return defaultValue;
    }
}

void KoResourceBundle::addResource(QString resourceType, QString filePath, QVector<KisTagSP> fileTagList, const QString md5sum, const int resourceId, const QString filenameInBundle)
{
    QStringList tags;
    Q_FOREACH(KisTagSP tag, fileTagList) {
        tags << tag->url();
    }
    m_manifest.addResource(resourceType, filePath, tags, md5sum, resourceId, filenameInBundle);
}

QList<QString> KoResourceBundle::getTagsList()
{
#if QT_VERSION >= QT_VERSION_CHECK(5,14,0)
    return QList<QString>(m_bundletags.begin(), m_bundletags.end());
#else
    return QList<QString>::fromSet(m_bundletags);
#endif
}

QStringList KoResourceBundle::resourceTypes() const
{
    return m_manifest.types();
}

void KoResourceBundle::setThumbnail(QString filename)
{
    if (QFileInfo(filename).exists()) {
        m_thumbnail = QImage(filename);
        m_thumbnail = m_thumbnail.scaled(256, 256, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    }
    else {
        m_thumbnail = QImage(256, 256, QImage::Format_ARGB32);
        QPainter gc(&m_thumbnail);
        gc.fillRect(0, 0, 256, 256, Qt::red);
        gc.end();
    }
}

void KoResourceBundle::writeMeta(const QString &metaTag, KoXmlWriter *writer)
{
    if (m_metadata.contains(metaTag)) {
        QByteArray mt = metaTag.toUtf8();
        QByteArray tx = m_metadata[metaTag].toUtf8();
        writer->startElement(mt);
        writer->addTextNode(tx);
        writer->endElement();
    }
}

void KoResourceBundle::writeUserDefinedMeta(const QString &metaTag, KoXmlWriter *writer)
{
    if (m_metadata.contains(metaTag)) {
        writer->startElement("meta:meta-userdefined");
        writer->addAttribute("meta:name", metaTag);
        writer->addAttribute("meta:value", m_metadata[metaTag]);
        writer->endElement();
    }
}

bool KoResourceBundle::readMetaData(KoStore *resourceStore)
{
    const QString metaPath = prefixedPath(m_rootPrefix, "meta.xml");
    if (resourceStore->open(metaPath)) {
        QDomDocument doc;
        if (!doc.setContent(resourceStore->device())) {
            qWarning() << "Could not parse meta.xml for" << m_filename;
            return false;
        }
        // First find the manifest:manifest node.
        QDomNode n = doc.firstChild();
        for (; !n.isNull(); n = n.nextSibling()) {
            if (!n.isElement()) {
                continue;
            }
            if (n.toElement().tagName() == "meta:meta") {
                break;
            }
        }

        if (n.isNull()) {
            qWarning() << "Could not find manifest node for bundle" << m_filename;
            return false;
        }

        const QDomElement  metaElement = n.toElement();
        for (n = metaElement.firstChild(); !n.isNull(); n = n.nextSibling()) {
            if (n.isElement()) {
                QDomElement e = n.toElement();
                if (e.tagName() == "meta:meta-userdefined") {
                    if (e.attribute("meta:name") == "tag") {
                        m_bundletags << e.attribute("meta:value");
                    }
                    else {
                        QString metaName = e.attribute("meta:name");
                        if (!metaName.startsWith("meta:") && !metaName.startsWith("dc:")) {
                            if (metaName == "email" || metaName == "license" || metaName == "website") { // legacy metadata options
                                if (!m_metadata.contains("meta:" + metaName)) {
                                    m_metadata.insert("meta:" + metaName, e.attribute("meta:value"));
                                }
                            } else {
                                qWarning() << "Unrecognized metadata: " << e.tagName() << e.attribute("meta:name") << e.attribute("meta:value");
                            }
                        }
                        m_metadata.insert(e.attribute("meta:name"), e.attribute("meta:value"));
                    }
                }
                else {
                    if (!m_metadata.contains(e.tagName())) {
                        m_metadata.insert(e.tagName(), e.firstChild().toText().data());
                    }
                }
            }
        }
        resourceStore->close();
        return true;
    }
    return false;
}

void KoResourceBundle::saveMetadata(QScopedPointer<KoStore> &store)
{
    QBuffer buf;

    store->open("meta.xml");
    buf.open(QBuffer::WriteOnly);

    KoXmlWriter metaWriter(&buf);
    metaWriter.startDocument("office:document-meta");
    metaWriter.startElement("meta:meta");

    writeMeta(KisResourceStorage::s_meta_generator, &metaWriter);

    QByteArray ba1 = KisResourceStorage::s_meta_version.toUtf8();
    metaWriter.startElement(ba1);
    QByteArray ba2  = m_bundleVersion.toUtf8();
    metaWriter.addTextNode(ba2);
    metaWriter.endElement();

    writeMeta(KisResourceStorage::s_meta_author, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_title,  &metaWriter);
    writeMeta(KisResourceStorage::s_meta_description, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_initial_creator,  &metaWriter);
    writeMeta(KisResourceStorage::s_meta_creator, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_creation_date, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_dc_date, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_email, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_license, &metaWriter);
    writeMeta(KisResourceStorage::s_meta_website, &metaWriter);

    // For compatibility
    writeUserDefinedMeta("email", &metaWriter);
    writeUserDefinedMeta("license", &metaWriter);
    writeUserDefinedMeta("website", &metaWriter);


    Q_FOREACH (const QString &tag, m_bundletags) {
        QByteArray ba1 = KisResourceStorage::s_meta_user_defined.toUtf8();
        QByteArray ba2 = KisResourceStorage::s_meta_name.toUtf8();
        QByteArray ba3 = KisResourceStorage::s_meta_value.toUtf8();
        metaWriter.startElement(ba1);
        metaWriter.addAttribute(ba2, "tag");
        metaWriter.addAttribute(ba3, tag);
        metaWriter.endElement();
    }

    metaWriter.endElement(); // meta:meta
    metaWriter.endDocument();

    buf.close();
    store->write(buf.data());
    store->close();
}

void KoResourceBundle::saveManifest(QScopedPointer<KoStore> &store)
{
    store->open("META-INF/manifest.xml");
    QBuffer buf;
    buf.open(QBuffer::WriteOnly);
    m_manifest.save(&buf);
    buf.close();
    store->write(buf.data());
    store->close();
}

QString KoResourceBundle::manifestOverridePath() const
{
    return ::manifestOverridePath(m_filename);
}

bool KoResourceBundle::saveManifestOverride()
{
    const QString path = manifestOverridePath();
    QFileInfo info(path);
    QDir dir(info.path());
    if (!dir.exists() && !dir.mkpath(".")) {
        qWarning() << "Could not create manifest override path" << info.path();
        return false;
    }

    KoResourceBundleManifest fixedManifest;
    Q_FOREACH (const QString &type, m_manifest.types()) {
        Q_FOREACH (const KoResourceBundleManifest::ResourceReference &ref, m_manifest.files(type)) {
            QString filenameInBundle = ref.filenameInBundle;
            if (filenameInBundle.startsWith(type + "/")) {
                filenameInBundle = filenameInBundle.mid(type.length() + 1);
            } else if (ref.resourcePath.startsWith(type + "/")) {
                filenameInBundle = ref.resourcePath.mid(type.length() + 1);
            }
            const QString md5sum = normalizeMd5String(ref.md5sum);
            fixedManifest.addResource(type, ref.resourcePath, ref.tagList, md5sum, ref.resourceId, filenameInBundle);
        }
    }

    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        qWarning() << "Could not open manifest override for writing" << path;
        return false;
    }

    if (!fixedManifest.save(&file)) {
        qWarning() << "Could not save manifest override for bundle" << m_filename;
        return false;
    }

    if (!file.commit()) {
        qWarning() << "Could not commit manifest override for bundle" << m_filename;
        return false;
    }

    m_manifestDirty = false;
    m_manifestOverrideLoaded = true;
    return true;
}

int KoResourceBundle::resourceCount() const
{
    return m_manifest.files().count();
}

KoResourceBundleManifest &KoResourceBundle::manifest()
{
    return m_manifest;
}

KoResourceSP KoResourceBundle::resource(const QString &resourceType, const QString &filepath)
{
    QString mime = KisMimeDatabase::mimeTypeForSuffix(filepath);
    KisResourceLoaderBase *loader = KisResourceLoaderRegistry::instance()->loader(resourceType, mime);
    if (!loader) {
        qWarning() << "Could not create loader for" << resourceType << filepath << mime;
        return 0;
    }

#if (QT_VERSION >= QT_VERSION_CHECK(5, 14, 0))
    QStringList parts = filepath.split('/', Qt::SkipEmptyParts);
#else
    QStringList parts = filepath.split('/', QString::SkipEmptyParts);
#endif

    Q_ASSERT(parts.size() == 2);

    KoResourceSP resource = loader->create(parts[1]);
    return loadResource(resource) ? resource : 0;
}

bool KoResourceBundle::exportResource(const QString &resourceType, const QString &fileName, QIODevice *device)
{
    if (m_filename.isEmpty()) return false;

    QScopedPointer<KoStore> resourceStore(KoStore::createStore(m_filename, KoStore::Read, "application/x-krita-resourcebundle", KoStore::Zip));

    if (!resourceStore || resourceStore->bad()) {
        qWarning() << "Could not open store on bundle" << m_filename;
        return false;
    }
    if (m_rootPrefix.isEmpty()) {
        m_rootPrefix = ensureTrailingSlash(detectRootPrefix(resourceStore.data()));
    }
    const QString filePath = QString("%1/%2").arg(resourceType).arg(fileName);

    const QString storePath = prefixedPath(m_rootPrefix, filePath);
    if (!resourceStore->open(storePath)) {
        qWarning() << "Could not open file in bundle" << filePath;
        return false;
    }

    device->write(resourceStore->device()->readAll());

    return true;
}

bool KoResourceBundle::loadResource(KoResourceSP resource)
{
    if (m_filename.isEmpty()) return false;

    const QString resourceType = resource->resourceType().first;

    QScopedPointer<KoStore> resourceStore(KoStore::createStore(m_filename, KoStore::Read, "application/x-krita-resourcebundle", KoStore::Zip));

    if (!resourceStore || resourceStore->bad()) {
        qWarning() << "Could not open store on bundle" << m_filename;
        return false;
    }
    if (m_rootPrefix.isEmpty()) {
        m_rootPrefix = ensureTrailingSlash(detectRootPrefix(resourceStore.data()));
    }
    const QString fileName = QString("%1/%2").arg(resourceType).arg(resource->filename());

    const QString storePath = prefixedPath(m_rootPrefix, fileName);
    if (!resourceStore->open(storePath)) {
        qWarning() << "Could not open file in bundle" << fileName;
        m_manifest.removeFile(fileName);
        m_manifestDirty = true;
        saveManifestOverride();
        return false;
    }

    if (resourceStore->size() == 0) {
        qWarning() << "Resource file is empty in bundle" << fileName;
        resourceStore->close();
        m_manifest.removeFile(fileName);
        m_manifestDirty = true;
        saveManifestOverride();
        return false;
    }

    if (!resource->loadFromDevice(resourceStore->device(),
                                  KisGlobalResourcesInterface::instance())) {
        qWarning() << "Could not load the resource from the bundle" << resourceType << fileName << m_filename;
        resourceStore->close();
        m_manifest.removeFile(fileName);
        m_manifestDirty = true;
        saveManifestOverride();
        return false;
    }

    resourceStore->close();

    if ((resource->image().isNull() || resource->thumbnail().isNull()) && !resource->thumbnailPath().isNull()) {

        const QString thumbnailPath = prefixedPath(m_rootPrefix, resourceType + '/' + resource->thumbnailPath());
        if (!resourceStore->open(thumbnailPath)) {
            qWarning() << "Could not open thumbnail in bundle" << resource->thumbnailPath();
            return false;
        }

        QImage img;
        img.load(resourceStore->device(), QFileInfo(resource->thumbnailPath()).completeSuffix().toLatin1());
        resource->setImage(img);
        resource->updateThumbnail();

        resourceStore->close();
    }

    return true;
}

QString KoResourceBundle::resourceMd5(const QString &url)
{
    QString result;

    if (m_filename.isEmpty()) return result;

    QScopedPointer<KoStore> resourceStore(KoStore::createStore(m_filename, KoStore::Read, "application/x-krita-resourcebundle", KoStore::Zip));

    if (!resourceStore || resourceStore->bad()) {
        qWarning() << "Could not open store on bundle" << m_filename;
        return result;
    }
    if (m_rootPrefix.isEmpty()) {
        m_rootPrefix = ensureTrailingSlash(detectRootPrefix(resourceStore.data()));
    }
    if (!resourceStore->open(prefixedPath(m_rootPrefix, url))) {
        qWarning() << "Could not open file in bundle" << url;
        return result;
    }

    result = KoMD5Generator::generateHash(resourceStore->device());
    resourceStore->close();

    return result;
}

QImage KoResourceBundle::image() const
{
    return m_thumbnail;
}

QString KoResourceBundle::filename() const
{
    return m_filename;
}
