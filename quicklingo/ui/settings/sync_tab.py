from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings.oauth_connect_dialog import run_oauth_connect
from quicklingo.ui.settings_theme import (
    align_form_labels,
    configure_api_key_hint,
    configure_api_key_label,
    configure_password_field,
    configure_settings_card,
    configure_settings_group_box,
    style_api_key_hint_text,
)

OAUTH_TRANSPORTS = frozenset({"google_drive", "dropbox", "onedrive"})


class SyncTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("settingsTabBody")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        connection_card = QWidget()
        configure_settings_card(connection_card)
        self._connection_form = QFormLayout(connection_card)
        self._connection_form.setContentsMargins(15, 15, 15, 15)
        self._connection_form.setVerticalSpacing(10)
        self._connection_form.setHorizontalSpacing(10)
        self._connection_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self._connection_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._transport_label = QLabel()
        configure_api_key_label(self._transport_label, spaced=False)
        self._transport_combo = QComboBox()
        for value in ("", "webdav", "google_drive", "dropbox", "onedrive"):
            self._transport_combo.addItem("", value)
        self._transport_combo.currentIndexChanged.connect(self._on_transport_changed)
        self._transport_combo.currentIndexChanged.connect(self.mark_dirty)

        self._migration_note = QLabel()
        self._migration_note.setWordWrap(True)
        self._migration_note.setObjectName("apiKeyNote")

        self._webdav_url_label = QLabel()
        configure_api_key_label(self._webdav_url_label)
        self._webdav_url_field = QLineEdit()
        self._webdav_url_field.textChanged.connect(self.mark_dirty)
        self._webdav_user_label = QLabel()
        configure_api_key_label(self._webdav_user_label)
        self._webdav_user_field = QLineEdit()
        self._webdav_user_field.textChanged.connect(self.mark_dirty)
        self._webdav_pass_label = QLabel()
        configure_api_key_label(self._webdav_pass_label)
        self._webdav_pass_field = QLineEdit()
        configure_password_field(self._webdav_pass_field)
        self._webdav_pass_field.textChanged.connect(self.mark_dirty)
        self._webdav_hint = QLabel()
        configure_api_key_hint(self._webdav_hint)

        self._google_client_id_label = QLabel()
        configure_api_key_label(self._google_client_id_label)
        self._google_client_id_field = QLineEdit()
        self._google_client_id_field.textChanged.connect(self.mark_dirty)
        self._google_client_secret_label = QLabel()
        configure_api_key_label(self._google_client_secret_label)
        self._google_client_secret_field = QLineEdit()
        configure_password_field(self._google_client_secret_field)
        self._google_client_secret_field.textChanged.connect(self.mark_dirty)
        self._google_hint = QLabel()
        configure_api_key_hint(self._google_hint)
        self._google_account_label = QLabel()
        configure_api_key_label(self._google_account_label)
        self._google_account_value = QLabel()
        self._google_connect_btn = QPushButton()
        self._google_connect_btn.setObjectName("btnSecondary")
        self._google_connect_btn.clicked.connect(lambda: self._connect_oauth("google_drive"))
        self._google_disconnect_btn = QPushButton()
        self._google_disconnect_btn.setObjectName("btnSecondary")
        self._google_disconnect_btn.clicked.connect(lambda: self._disconnect_oauth("google_drive"))
        self._google_actions = self._action_row(
            self._google_connect_btn,
            self._google_disconnect_btn,
        )

        self._dropbox_app_key_label = QLabel()
        configure_api_key_label(self._dropbox_app_key_label)
        self._dropbox_app_key_field = QLineEdit()
        self._dropbox_app_key_field.textChanged.connect(self.mark_dirty)
        self._dropbox_app_secret_label = QLabel()
        configure_api_key_label(self._dropbox_app_secret_label)
        self._dropbox_app_secret_field = QLineEdit()
        configure_password_field(self._dropbox_app_secret_field)
        self._dropbox_app_secret_field.textChanged.connect(self.mark_dirty)
        self._dropbox_hint = QLabel()
        configure_api_key_hint(self._dropbox_hint)
        self._dropbox_account_label = QLabel()
        configure_api_key_label(self._dropbox_account_label)
        self._dropbox_account_value = QLabel()
        self._dropbox_connect_btn = QPushButton()
        self._dropbox_connect_btn.setObjectName("btnSecondary")
        self._dropbox_connect_btn.clicked.connect(lambda: self._connect_oauth("dropbox"))
        self._dropbox_disconnect_btn = QPushButton()
        self._dropbox_disconnect_btn.setObjectName("btnSecondary")
        self._dropbox_disconnect_btn.clicked.connect(lambda: self._disconnect_oauth("dropbox"))
        self._dropbox_actions = self._action_row(
            self._dropbox_connect_btn,
            self._dropbox_disconnect_btn,
        )

        self._onedrive_client_id_label = QLabel()
        configure_api_key_label(self._onedrive_client_id_label)
        self._onedrive_client_id_field = QLineEdit()
        self._onedrive_client_id_field.textChanged.connect(self.mark_dirty)
        self._onedrive_hint = QLabel()
        configure_api_key_hint(self._onedrive_hint)
        self._onedrive_account_label = QLabel()
        configure_api_key_label(self._onedrive_account_label)
        self._onedrive_account_value = QLabel()
        self._onedrive_connect_btn = QPushButton()
        self._onedrive_connect_btn.setObjectName("btnSecondary")
        self._onedrive_connect_btn.clicked.connect(lambda: self._connect_oauth("onedrive"))
        self._onedrive_disconnect_btn = QPushButton()
        self._onedrive_disconnect_btn.setObjectName("btnSecondary")
        self._onedrive_disconnect_btn.clicked.connect(lambda: self._disconnect_oauth("onedrive"))
        self._onedrive_actions = self._action_row(
            self._onedrive_connect_btn,
            self._onedrive_disconnect_btn,
        )

        self._privacy_note = QLabel()
        self._privacy_note.setWordWrap(True)
        self._privacy_note.setObjectName("apiKeyNote")

        self._connection_form.addRow(self._transport_label, self._transport_combo)
        self._connection_form.addRow(self._migration_note)
        self._connection_form.addRow(self._webdav_url_label, self._webdav_url_field)
        self._connection_form.addRow(self._webdav_user_label, self._webdav_user_field)
        self._connection_form.addRow(self._webdav_pass_label, self._webdav_pass_field)
        self._connection_form.addRow(self._webdav_hint)
        self._connection_form.addRow(self._google_client_id_label, self._google_client_id_field)
        self._connection_form.addRow(
            self._google_client_secret_label,
            self._google_client_secret_field,
        )
        self._connection_form.addRow(self._google_hint)
        self._connection_form.addRow(self._google_account_label, self._google_account_value)
        self._connection_form.addRow(self._google_actions)
        self._connection_form.addRow(self._dropbox_app_key_label, self._dropbox_app_key_field)
        self._connection_form.addRow(
            self._dropbox_app_secret_label,
            self._dropbox_app_secret_field,
        )
        self._connection_form.addRow(self._dropbox_hint)
        self._connection_form.addRow(self._dropbox_account_label, self._dropbox_account_value)
        self._connection_form.addRow(self._dropbox_actions)
        self._connection_form.addRow(
            self._onedrive_client_id_label,
            self._onedrive_client_id_field,
        )
        self._connection_form.addRow(self._onedrive_hint)
        self._connection_form.addRow(self._onedrive_account_label, self._onedrive_account_value)
        self._connection_form.addRow(self._onedrive_actions)
        self._connection_form.addRow(self._privacy_note)

        self._status_group = QGroupBox()
        configure_settings_group_box(self._status_group)
        self._status_form = QFormLayout(self._status_group)
        self._device_id_label = QLabel()
        configure_api_key_label(self._device_id_label, spaced=False)
        self._device_id_value = QLabel()
        self._device_id_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._last_sync_label = QLabel()
        configure_api_key_label(self._last_sync_label)
        self._last_sync_value = QLabel()
        self._last_status_label = QLabel()
        configure_api_key_label(self._last_status_label)
        self._last_status_value = QLabel()
        self._labels = [
            self._transport_label,
            self._webdav_url_label,
            self._webdav_user_label,
            self._webdav_pass_label,
            self._google_client_id_label,
            self._google_client_secret_label,
            self._google_account_label,
            self._dropbox_app_key_label,
            self._dropbox_app_secret_label,
            self._dropbox_account_label,
            self._onedrive_client_id_label,
            self._onedrive_account_label,
            self._device_id_label,
            self._last_sync_label,
            self._last_status_label,
        ]
        self._status_form.addRow(self._device_id_label, self._device_id_value)
        self._status_form.addRow(self._last_sync_label, self._last_sync_value)
        self._status_form.addRow(self._last_status_label, self._last_status_value)

        content_layout.addWidget(connection_card)
        content_layout.addWidget(self._status_group)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.reload()
        self.retranslate_ui()

    def _action_row(self, connect_btn: QPushButton, disconnect_btn: QPushButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(connect_btn)
        layout.addWidget(disconnect_btn)
        layout.addStretch()
        return row

    def retranslate_ui(self) -> None:
        transport_labels = {
            "": tr("settings.sync.transport_none"),
            "webdav": tr("settings.sync.transport_webdav"),
            "google_drive": tr("settings.sync.transport_google"),
            "dropbox": tr("settings.sync.transport_dropbox"),
            "onedrive": tr("settings.sync.transport_onedrive"),
        }
        self._transport_label.setText(tr("settings.sync.transport"))
        for index in range(self._transport_combo.count()):
            value = self._transport_combo.itemData(index)
            self._transport_combo.setItemText(index, transport_labels.get(value, ""))
        self._migration_note.setText(tr("settings.sync.migration_note"))
        self._webdav_url_label.setText(tr("settings.sync.webdav_url"))
        self._webdav_user_label.setText(tr("settings.sync.webdav_username"))
        self._webdav_pass_label.setText(tr("settings.sync.webdav_password"))
        self._webdav_hint.setText(style_api_key_hint_text(tr("settings.sync.webdav_hint")))
        self._google_client_id_label.setText(tr("settings.sync.google_client_id"))
        self._google_client_secret_label.setText(tr("settings.sync.google_client_secret"))
        self._google_hint.setText(style_api_key_hint_text(tr("settings.sync.google_hint")))
        self._google_account_label.setText(tr("settings.sync.account"))
        self._google_connect_btn.setText(tr("settings.sync.connect"))
        self._google_disconnect_btn.setText(tr("settings.sync.disconnect"))
        self._dropbox_app_key_label.setText(tr("settings.sync.dropbox_app_key"))
        self._dropbox_app_secret_label.setText(tr("settings.sync.dropbox_app_secret"))
        self._dropbox_hint.setText(style_api_key_hint_text(tr("settings.sync.dropbox_hint")))
        self._dropbox_account_label.setText(tr("settings.sync.account"))
        self._dropbox_connect_btn.setText(tr("settings.sync.connect"))
        self._dropbox_disconnect_btn.setText(tr("settings.sync.disconnect"))
        self._onedrive_client_id_label.setText(tr("settings.sync.onedrive_client_id"))
        self._onedrive_hint.setText(style_api_key_hint_text(tr("settings.sync.onedrive_hint")))
        self._onedrive_account_label.setText(tr("settings.sync.account"))
        self._onedrive_connect_btn.setText(tr("settings.sync.connect"))
        self._onedrive_disconnect_btn.setText(tr("settings.sync.disconnect"))
        self._privacy_note.setText(tr("settings.sync.privacy_note"))
        self._status_group.setTitle(tr("settings.sync.status_group"))
        self._device_id_label.setText(tr("settings.sync.device_id"))
        self._last_sync_label.setText(tr("settings.sync.last_sync"))
        self._last_status_label.setText(tr("settings.sync.last_status"))
        align_form_labels(self._labels)
        self._refresh_account_labels()
        self._refresh_status_labels()

    def reload(self) -> None:
        self._transport_combo.blockSignals(True)
        index = self._transport_combo.findData(settings.get_sync_transport())
        if index >= 0:
            self._transport_combo.setCurrentIndex(index)
        self._transport_combo.blockSignals(False)
        self._webdav_url_field.setText(settings.get_sync_webdav_url())
        self._webdav_user_field.setText(settings.get_sync_webdav_username())
        self._webdav_pass_field.setText(settings.get_sync_webdav_password())
        self._google_client_id_field.setText(settings.get_sync_google_client_id())
        self._google_client_secret_field.setText(settings.get_sync_google_client_secret())
        self._dropbox_app_key_field.setText(settings.get_sync_dropbox_app_key())
        self._dropbox_app_secret_field.setText(settings.get_sync_dropbox_app_secret())
        self._onedrive_client_id_field.setText(settings.get_sync_onedrive_client_id())
        self._device_id_value.setText(settings.get_sync_device_id())
        self._on_transport_changed()
        self._refresh_account_labels()
        self._refresh_status_labels()
        self.mark_clean()

    def save(self) -> bool:
        settings.save_sync_transport(self._transport_combo.currentData())
        settings.save_sync_webdav_url(self._webdav_url_field.text())
        settings.save_sync_webdav_username(self._webdav_user_field.text())
        settings.save_sync_webdav_password(self._webdav_pass_field.text())
        settings.save_sync_google_client_id(self._google_client_id_field.text())
        settings.save_sync_google_client_secret(self._google_client_secret_field.text())
        settings.save_sync_dropbox_app_key(self._dropbox_app_key_field.text())
        settings.save_sync_dropbox_app_secret(self._dropbox_app_secret_field.text())
        settings.save_sync_onedrive_client_id(self._onedrive_client_id_field.text())
        self.mark_clean()
        return True

    def _connect_oauth(self, provider: str) -> None:
        if not self.save():
            return
        if run_oauth_connect(self, provider):
            self._refresh_account_labels()
            self.mark_clean()

    def _disconnect_oauth(self, provider: str) -> None:
        settings.clear_sync_oauth_tokens(provider)
        self._refresh_account_labels()

    def _refresh_account_labels(self) -> None:
        self._set_account_value(
            self._google_account_value,
            settings.get_sync_oauth_account("google_drive"),
        )
        self._set_account_value(
            self._dropbox_account_value,
            settings.get_sync_oauth_account("dropbox"),
        )
        self._set_account_value(
            self._onedrive_account_value,
            settings.get_sync_oauth_account("onedrive"),
        )

    @staticmethod
    def _set_account_value(label: QLabel, account: str) -> None:
        label.setText(account or tr("settings.sync.not_connected"))

    def _on_transport_changed(self) -> None:
        transport = self._transport_combo.currentData()
        is_webdav = transport == "webdav"
        is_google = transport == "google_drive"
        is_dropbox = transport == "dropbox"
        is_onedrive = transport == "onedrive"
        self._migration_note.setVisible(not transport)

        for widget, visible in (
            (self._webdav_url_label, is_webdav),
            (self._webdav_url_field, is_webdav),
            (self._webdav_user_label, is_webdav),
            (self._webdav_user_field, is_webdav),
            (self._webdav_pass_label, is_webdav),
            (self._webdav_pass_field, is_webdav),
            (self._webdav_hint, is_webdav),
            (self._google_client_id_label, is_google),
            (self._google_client_id_field, is_google),
            (self._google_client_secret_label, is_google),
            (self._google_client_secret_field, is_google),
            (self._google_hint, is_google),
            (self._google_account_label, is_google),
            (self._google_account_value, is_google),
            (self._google_actions, is_google),
            (self._dropbox_app_key_label, is_dropbox),
            (self._dropbox_app_key_field, is_dropbox),
            (self._dropbox_app_secret_label, is_dropbox),
            (self._dropbox_app_secret_field, is_dropbox),
            (self._dropbox_hint, is_dropbox),
            (self._dropbox_account_label, is_dropbox),
            (self._dropbox_account_value, is_dropbox),
            (self._dropbox_actions, is_dropbox),
            (self._onedrive_client_id_label, is_onedrive),
            (self._onedrive_client_id_field, is_onedrive),
            (self._onedrive_hint, is_onedrive),
            (self._onedrive_account_label, is_onedrive),
            (self._onedrive_account_value, is_onedrive),
            (self._onedrive_actions, is_onedrive),
        ):
            widget.setVisible(visible)

    def _refresh_status_labels(self) -> None:
        last_sync = settings.get_sync_last_sync_at()
        self._last_sync_value.setText(last_sync or tr("settings.sync.never"))
        status = settings.get_sync_last_sync_status()
        self._last_status_value.setText(status or tr("settings.sync.never"))

    def refresh_status(self) -> None:
        self._refresh_status_labels()
