import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import { Icon } from 'leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import 'leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css';
import 'leaflet-defaulticon-compatibility';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Textarea } from './components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { Slider } from './components/ui/slider';
import { Badge } from './components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from './components/ui/avatar';
import { MapPin, Heart, User, Settings, Home, Phone } from 'lucide-react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Custom icons for markers
const metroIcon = new Icon({
  iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIGZpbGw9IiNEQzI2MjYiLz4KPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHg9IjQiIHk9IjQiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSI+CjxwYXRoIGQ9Ik0yIDJoMTJ2MTJIMnoiIGZpbGw9IiNmZmZmZmYiLz4KPHBhdGggZD0iTTQgNGg4djhoLTh6IiBmaWxsPSIjREMyNjI2Ii8+CjwvZz4KPC9zdmc+',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

const propertyIcon = new Icon({
  iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDJMMTggNmwwIDEwLTggNGwtOC00bDAtMTB6IiBmaWxsPSIjMjU2M0VCIi8+Cjxwb2x5Z29uIHBvaW50cz0iMTAsNiAxNCw4IDE0LDE0IDEwLDE2IDYsMTQgNiw4IiBmaWxsPSIjZmZmZmZmIi8+Cjwvc3ZnPg==',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -10]
});

const App = () => {
  const [currentView, setCurrentView] = useState('profile');
  const [userProfile, setUserProfile] = useState(null);
  const [metroStations, setMetroStations] = useState([]);
  const [properties, setProperties] = useState([]);
  const [selectedStation, setSelectedStation] = useState(null);
  const [searchRadius, setSearchRadius] = useState(2.0);
  const [loading, setLoading] = useState(false);
  const [likedProperties, setLikedProperties] = useState(new Set());
  const [telegramUser, setTelegramUser] = useState(null);
  const mapRef = useRef(null);

  // Profile form data
  const [profileForm, setProfileForm] = useState({
    name: '',
    gender: '',
    age: '',
    about: '',
    preferred_location: '',
    search_radius_km: 2.0
  });

  // Moscow center coordinates
  const moscowCenter = [55.7558, 37.6176];

  // Initialize Telegram WebApp
  useEffect(() => {
    if (window.Telegram && window.Telegram.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      
      // Get user data from Telegram
      if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        const user = tg.initDataUnsafe.user;
        setTelegramUser(user);
        
        // Update profile form with Telegram data
        setProfileForm(prev => ({
          ...prev,
          name: user.first_name + (user.last_name ? ' ' + user.last_name : '')
        }));
      }
    } else {
      // For development - simulate Telegram user
      setTelegramUser({
        id: 123456789,
        first_name: 'Иван',
        last_name: 'Петров',
        username: 'ivan_petrov'
      });
      setProfileForm(prev => ({
        ...prev,
        name: 'Иван Петров'
      }));
    }
  }, []);

  // Load metro stations
  useEffect(() => {
    const loadMetroStations = async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/metro-stations`);
        setMetroStations(response.data);
      } catch (error) {
        console.error('Error loading metro stations:', error);
      }
    };

    loadMetroStations();
  }, []);

  // Load user profile if exists
  useEffect(() => {
    const loadUserProfile = async () => {
      if (!telegramUser) return;
      
      try {
        const response = await axios.get(`${BACKEND_URL}/api/user/profile/${telegramUser.id}`);
        const profile = response.data;
        setUserProfile(profile);
        setProfileForm({
          name: profile.name,
          gender: profile.gender || '',
          age: profile.age || '',
          about: profile.about || '',
          preferred_location: profile.preferred_location || '',
          search_radius_km: profile.search_radius_km || 2.0
        });
        setSearchRadius(profile.search_radius_km || 2.0);
      } catch (error) {
        if (error.response?.status !== 404) {
          console.error('Error loading user profile:', error);
        }
      }
    };

    loadUserProfile();
  }, [telegramUser]);

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    if (!telegramUser) return;

    try {
      const profileData = {
        telegram_id: telegramUser.id,
        name: profileForm.name,
        photo_url: telegramUser.photo_url || null,
        gender: profileForm.gender || null,
        age: profileForm.age ? parseInt(profileForm.age) : null,
        about: profileForm.about || null,
        preferred_location: profileForm.preferred_location || null,
        search_radius_km: profileForm.search_radius_km
      };

      await axios.post(`${BACKEND_URL}/api/user/profile`, profileData);
      setUserProfile(profileData);
      setSearchRadius(profileData.search_radius_km);
      setCurrentView('map');
    } catch (error) {
      console.error('Error saving profile:', error);
      alert('Ошибка при сохранении профиля');
    }
  };

  const handleStationClick = async (station) => {
    setSelectedStation(station);
    setLoading(true);

    try {
      const response = await axios.get(`${BACKEND_URL}/api/properties/near-metro`, {
        params: {
          station_name: station.name,
          radius_km: searchRadius
        }
      });
      setProperties(response.data);
    } catch (error) {
      console.error('Error loading properties:', error);
      setProperties([]);
    } finally {
      setLoading(false);
    }
  };

  const handleLikeProperty = async (propertyId) => {
    if (!telegramUser) return;

    try {
      await axios.post(`${BACKEND_URL}/api/properties/${propertyId}/like`, {
        property_id: propertyId,
        telegram_id: telegramUser.id
      });
      
      setLikedProperties(prev => new Set(prev).add(propertyId));
      
      // Show contact info after liking
      const contactResponse = await axios.get(
        `${BACKEND_URL}/api/properties/${propertyId}/contact?telegram_id=${telegramUser.id}`
      );
      
      alert(`Контакт: ${contactResponse.data.contact_info}`);
    } catch (error) {
      console.error('Error liking property:', error);
    }
  };

  const renderProfileView = () => (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <Card>
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Avatar className="h-20 w-20">
              <AvatarImage src={telegramUser?.photo_url} />
              <AvatarFallback>
                <User className="h-10 w-10" />
              </AvatarFallback>
            </Avatar>
          </div>
          <CardTitle className="text-2xl text-gray-800">Создание профиля</CardTitle>
          <p className="text-gray-600">Расскажите о себе для поиска жилья</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleProfileSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Имя</Label>
              <Input
                id="name"
                value={profileForm.name}
                onChange={(e) => setProfileForm(prev => ({ ...prev, name: e.target.value }))}
                required
              />
            </div>

            <div>
              <Label htmlFor="gender">Пол</Label>
              <Select
                value={profileForm.gender}
                onValueChange={(value) => setProfileForm(prev => ({ ...prev, gender: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите пол" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="male">Мужской</SelectItem>
                  <SelectItem value="female">Женский</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="age">Возраст</Label>
              <Input
                id="age"
                type="number"
                value={profileForm.age}
                onChange={(e) => setProfileForm(prev => ({ ...prev, age: e.target.value }))}
                min="18"
                max="100"
              />
            </div>

            <div>
              <Label htmlFor="about">О себе</Label>
              <Textarea
                id="about"
                value={profileForm.about}
                onChange={(e) => setProfileForm(prev => ({ ...prev, about: e.target.value }))}
                placeholder="Расскажите о себе..."
                rows={3}
              />
            </div>

            <div>
              <Label htmlFor="preferred_location">Желаемый район</Label>
              <Input
                id="preferred_location"
                value={profileForm.preferred_location}
                onChange={(e) => setProfileForm(prev => ({ ...prev, preferred_location: e.target.value }))}
                placeholder="Например: Центр, Арбат, Сокольники..."
              />
            </div>

            <div>
              <Label>Радиус поиска: {profileForm.search_radius_km} км</Label>
              <Slider
                value={[profileForm.search_radius_km]}
                onValueChange={(value) => setProfileForm(prev => ({ ...prev, search_radius_km: value[0] }))}
                min={0.5}
                max={10}
                step={0.5}
                className="mt-2"
              />
            </div>

            <Button type="submit" className="w-full">
              Сохранить профиль
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );

  const renderMapView = () => (
    <div className="h-screen flex flex-col" key="map-view">
      {/* Header */}
      <div className="bg-white border-b p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-800">Поиск жилья в Москве</h1>
          <Badge variant="secondary">
            Радиус: {searchRadius} км
          </Badge>
        </div>
        {selectedStation && (
          <div className="mt-2 flex items-center space-x-2">
            <MapPin className="h-4 w-4 text-blue-600" />
            <span className="text-sm text-gray-600">
              {selectedStation.name} • Найдено: {properties.length} объявлений
            </span>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute top-4 right-4 z-[1000] bg-white p-3 rounded-lg shadow-lg">
            <div className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-blue-600 rounded-full border-t-transparent"></div>
              <span className="text-sm">Загружаем объявления...</span>
            </div>
          </div>
        )}
        
        <MapContainer
          key="moscow-map"
          ref={mapRef}
          center={moscowCenter}
          zoom={11}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={true}
          whenCreated={(map) => {
            mapRef.current = map;
          }}
        >
          <TileLayer
            attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {/* Metro station markers */}
          {metroStations.map((station) => (
            <Marker
              key={station.id}
              position={[station.location.coordinates[1], station.location.coordinates[0]]}
              icon={metroIcon}
              eventHandlers={{
                click: () => handleStationClick(station)
              }}
            >
              <Popup>
                <div className="p-2">
                  <h3 className="font-semibold text-gray-800">{station.name}</h3>
                  {station.name_en && (
                    <p className="text-sm text-gray-600 italic">{station.name_en}</p>
                  )}
                  <p className="text-sm text-gray-600 mb-2">
                    Линия: <span style={{ color: station.line_color }}>●</span> {station.line}
                  </p>
                  <Button 
                    size="sm" 
                    onClick={() => handleStationClick(station)}
                    className="w-full"
                  >
                    Найти жильё рядом
                  </Button>
                </div>
              </Popup>
            </Marker>
          ))}
          
          {/* Property markers */}
          {properties.map((property, index) => (
            <Marker
              key={`property-${index}`}
              position={[
                property.location?.coordinates[1] || property.coordinates[1],
                property.location?.coordinates[0] || property.coordinates[0]
              ]}
              icon={propertyIcon}
            >
              <Popup>
                <div className="p-2 max-w-sm">
                  <h4 className="font-semibold text-gray-800 mb-2">{property.title}</h4>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p><strong>Цена:</strong> {property.price?.toLocaleString()} ₽/месяц</p>
                    <p><strong>Адрес:</strong> {property.address}</p>
                    {property.area && <p><strong>Площадь:</strong> {property.area} м²</p>}
                    {property.rooms && <p><strong>Комнат:</strong> {property.rooms}</p>}
                    {property.distance_to_center && (
                      <p><strong>Расстояние:</strong> {property.distance_to_center} км</p>
                    )}
                    {property.description && (
                      <p className="mt-2 text-xs">{property.description}</p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => handleLikeProperty(property.id || property.source_url)}
                    disabled={likedProperties.has(property.id || property.source_url)}
                    className="w-full mt-3"
                    variant={likedProperties.has(property.id || property.source_url) ? "secondary" : "default"}
                  >
                    <Heart className={`h-4 w-4 mr-1 ${likedProperties.has(property.id || property.source_url) ? 'fill-current' : ''}`} />
                    {likedProperties.has(property.id || property.source_url) ? 'Понравилось' : 'Нравится'}
                  </Button>
                </div>
              </Popup>
            </Marker>
          ))}
          
          {/* Search radius circle */}
          {selectedStation && (
            <Circle
              center={[selectedStation.location.coordinates[1], selectedStation.location.coordinates[0]]}
              radius={searchRadius * 1000}
              color="#3B82F6"
              fillColor="#3B82F6"
              fillOpacity={0.1}
              weight={2}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );

  const renderSettingsView = () => (
    <div className="max-w-2xl mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="h-5 w-5" />
            <span>Настройки поиска</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Радиус поиска: {searchRadius} км</Label>
            <Slider
              value={[searchRadius]}
              onValueChange={(value) => setSearchRadius(value[0])}
              min={0.5}
              max={10}
              step={0.5}
              className="mt-2"
            />
          </div>
          
          {userProfile && (
            <div>
              <h3 className="font-semibold mb-2">Профиль пользователя</h3>
              <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                <p><strong>Имя:</strong> {userProfile.name}</p>
                {userProfile.gender && <p><strong>Пол:</strong> {userProfile.gender}</p>}
                {userProfile.age && <p><strong>Возраст:</strong> {userProfile.age}</p>}
                {userProfile.about && <p><strong>О себе:</strong> {userProfile.about}</p>}
                {userProfile.preferred_location && (
                  <p><strong>Предпочтения:</strong> {userProfile.preferred_location}</p>
                )}
              </div>
              <Button 
                variant="outline" 
                onClick={() => setCurrentView('profile')}
                className="mt-4"
              >
                Редактировать профиль
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  if (!telegramUser) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-blue-600 rounded-full border-t-transparent mx-auto mb-4"></div>
          <p>Инициализация Telegram WebApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {currentView !== 'map' && (
        <Tabs value={currentView} onValueChange={setCurrentView} className="w-full">
          <TabsList className="grid w-full grid-cols-3 sticky top-0 z-10 bg-white border-b">
            <TabsTrigger value="profile" className="flex items-center space-x-1">
              <User className="h-4 w-4" />
              <span>Профиль</span>
            </TabsTrigger>
            <TabsTrigger value="map" className="flex items-center space-x-1">
              <Home className="h-4 w-4" />
              <span>Карта</span>
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center space-x-1">
              <Settings className="h-4 w-4" />
              <span>Настройки</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="mt-0">
            {renderProfileView()}
          </TabsContent>

          <TabsContent value="settings" className="mt-0">
            {renderSettingsView()}
          </TabsContent>
        </Tabs>
      )}

      {currentView === 'map' && (
        <div className="relative">
          {renderMapView()}
          
          {/* Bottom navigation for map view */}
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-[1000]">
            <div className="bg-white rounded-full shadow-lg p-2 flex items-center space-x-1">
              <Button
                size="sm"
                variant={currentView === 'profile' ? 'default' : 'ghost'}
                onClick={() => setCurrentView('profile')}
              >
                <User className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant={currentView === 'map' ? 'default' : 'ghost'}
                onClick={() => setCurrentView('map')}
              >
                <Home className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant={currentView === 'settings' ? 'default' : 'ghost'}
                onClick={() => setCurrentView('settings')}
              >
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;