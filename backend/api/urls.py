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
    ComputedMeasureListView,
    ComputedMeasureDetailView,
    MeasureComputeView,
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

    # Méthodes de connexion disponibles
    path('connection-methods/',                       ConnectionMethodsView.as_view()),

    # Grandeurs calculées
    path('sensors/<int:pk>/measures/',                ComputedMeasureListView.as_view()),
    path('measures/<int:pk>/',                        ComputedMeasureDetailView.as_view()),
    path('measures/<int:pk>/compute/',                MeasureComputeView.as_view()),
]
