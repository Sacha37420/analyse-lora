from django.urls import path
from .views import (
    MeView,
    SensorListView,
    SensorDetailView,
    SensorUserAccessListView,
    SensorUserAccessDeleteView,
    SensorDataView,
    SensorConnectionView,
    ConnectionMethodsView,
    WebhookListView,
    WebhookDetailView,
    WebhookDataView,
    WebhookUserAccessListView,
    WebhookUserAccessDeleteView,
    ComputedMeasureListView,
    ComputedMeasureDetailView,
    MeasureComputeView,
)
from .dashboard import (
    DashboardGroupsView,
    DashboardFieldsView,
    DashboardChartView,
    DashboardGaugesView,
)

urlpatterns = [
    # Utilisateur courant
    path('me/', MeView.as_view()),

    # Capteurs
    path('sensors/',                                  SensorListView.as_view()),
    path('sensors/<int:pk>/',                         SensorDetailView.as_view()),
    path('sensors/<int:pk>/users/',                   SensorUserAccessListView.as_view()),
    path('sensors/<int:pk>/users/<str:email>/',       SensorUserAccessDeleteView.as_view()),
    path('sensors/<int:pk>/data/',                    SensorDataView.as_view()),
    path('sensors/<int:pk>/connection/',              SensorConnectionView.as_view()),

    # Webhooks (points d'ingestion partagés par plusieurs capteurs)
    path('webhooks/',                                 WebhookListView.as_view()),
    path('webhooks/<int:pk>/',                        WebhookDetailView.as_view()),
    path('webhooks/<int:pk>/data/',                   WebhookDataView.as_view()),
    path('webhooks/<int:pk>/users/',                  WebhookUserAccessListView.as_view()),
    path('webhooks/<int:pk>/users/<str:email>/',      WebhookUserAccessDeleteView.as_view()),

    # Méthodes de connexion disponibles
    path('connection-methods/',                       ConnectionMethodsView.as_view()),

    # Tableau de bord (regroupement par webhook / capteur autonome)
    path('dashboard/groups/',                                DashboardGroupsView.as_view()),
    path('dashboard/groups/<str:group_type>/<int:group_id>/fields/', DashboardFieldsView.as_view()),
    path('dashboard/groups/<str:group_type>/<int:group_id>/chart/',  DashboardChartView.as_view()),
    path('dashboard/groups/<str:group_type>/<int:group_id>/gauges/', DashboardGaugesView.as_view()),

    # Grandeurs calculées
    path('sensors/<int:pk>/measures/',                ComputedMeasureListView.as_view()),
    path('measures/<int:pk>/',                        ComputedMeasureDetailView.as_view()),
    path('measures/<int:pk>/compute/',                MeasureComputeView.as_view()),
]
