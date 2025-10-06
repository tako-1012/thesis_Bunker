using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Xml;
using System.Threading.Tasks;
using System.Collections.Generic;
using UnityEditor;
using Unity.EditorCoroutines.Editor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Unity.Robotics.UrdfImporter;
using Unity.Robotics.UrdfImporter.Control;

using UnitySensors.Sensor.Camera;
using UnitySensors.Sensor.LiDAR;
using UnitySensors.ROS.Publisher.Camera;
using  UnitySensors.ROS.Publisher.LiDAR;
using UnitySensors.ROS.Publisher.Image;
using UnitySensors.ROS.Publisher.PointCloud;
using UnitySensors.Sensor.IMU;
using UnitySensors.ROS.Publisher.IMU;
using UnitySensors.Sensor.GNSS;
using UnitySensors.ROS.Publisher.GNSS;

public class FileLogger
{
    private static string logFilePath = "debug_log.txt";

    public static void Log(string message)
    {
        File.AppendAllText(logFilePath, message + "\n");
    }
}

// 保存するためのXDrive設定用クラス
[System.Serializable]
public class XDriveSettings
{
    public string joint_name;
    public float stiffness;
    public float damping;
    public float forceLimit;

    public XDriveSettings(string joint_name, float stiffness, float damping, float forceLimit)
    {
        this.joint_name = joint_name;
        this.stiffness = stiffness;
        this.damping = damping;
        this.forceLimit = forceLimit;
    }
}

[InitializeOnLoad]
[ExecuteInEditMode]
public class RemoteCommandListener
{
    private static TcpListener listener = null;
    private static TcpClient client = null;
    private static bool isRunning = false;
    private static GameObject robotObject;

    private class StartUpData : ScriptableSingleton<StartUpData>
    {
        [SerializeField]
        private int _callCount;
        public bool IsStartUp()
        {
            return _callCount++ == 0;
        }
    }

    static RemoteCommandListener()
    {
        // エディタが完全に起動した後に初期化する
        EditorApplication.update += RemoteCommandListener.Initialize;
    }

    private static void Initialize()
    {
        // StartUpDataの初期化をInitialize内で行う
        if (!StartUpData.instance.IsStartUp())
            return;

        Start();
    }
    private static async void Start()
    {
        Debug.Log("Start Called...");
        if (Application.isPlaying)
        {
            return;
        }
        if (isRunning) return; // 多重起動防止
        isRunning = true;

        if (listener != null)
        {
            listener.Stop();
            listener = null;
        }
        listener = new TcpListener(IPAddress.Any, 5000);
        listener.Start();
        Debug.Log("Listening for URDF import commands...");

        try
        {
            if (client != null)
            {
                client.Close();
                client = null;
            }
            while (isRunning)
            {
                // listenerが停止された場合はループを終了
                if (!listener.Server.IsBound)
                    break;

                client = await listener.AcceptTcpClientAsync();
                if (client != null)
                {
                    HandleClient(client);
                }
            }
        }
        catch (ObjectDisposedException)
        {
            Debug.Log("Listener was stopped, ending listening loop.");
        }
        finally
        {
            // listenerが停止されている場合、終了処理を行う
            listener?.Stop();
        }
    }

    private static Task<GameObject> WaitForEditorCoroutine(IEnumerator<GameObject> coroutine)
    {
        var taskCompletionSource = new TaskCompletionSource<GameObject>();

        EditorCoroutineUtility.StartCoroutineOwnerless(HandleCoroutine(coroutine, taskCompletionSource));
        return taskCompletionSource.Task;
    }

    private static IEnumerator<GameObject> HandleCoroutine(IEnumerator<GameObject> coroutine, TaskCompletionSource<GameObject> tcs)
    {
        GameObject result = null;

        while (coroutine.MoveNext())
        {
            if (coroutine.Current is GameObject)
            {
                result = coroutine.Current as GameObject;
            }

            yield return coroutine.Current;
        }

        tcs.SetResult(result);
    }
    
    private static async void HandleClient(TcpClient client)
    {
        NetworkStream stream = client.GetStream();
        byte[] buffer = new byte[1024];
        int bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length);
        string commandString = Encoding.UTF8.GetString(buffer, 0, bytesRead);
        string[] commands = commandString.Split(' ');

        string urdfFilePath = commands[1];
        float robot_x = float.Parse(commands[2]);
        float robot_y = float.Parse(commands[3]);
        float robot_z = float.Parse(commands[4]);
        float robot_roll  = float.Parse(commands[5]) * Mathf.Rad2Deg;
        float robot_pitch = float.Parse(commands[6]) * Mathf.Rad2Deg;
        float robot_yaw   = float.Parse(commands[7]) * Mathf.Rad2Deg;
        bool robot_fixed = bool.Parse(commands[8]);

        Debug.Log("Received URDF path: " + urdfFilePath);

        EditorGUI.BeginChangeCheck();

        ImportSettings settings = new ImportSettings();
        //GameObject robotObject = UrdfRobotExtensions.CreateRuntime(urdfFilePath, settings);
        GameObject robotObject = await WaitForEditorCoroutine(
                UrdfRobotExtensions.Create(urdfFilePath, settings)
            );

        robotObject.AddComponent<PublishClock>();
        Vector3 newPosition = new Vector3(robot_x, robot_y, robot_z);
        robotObject.transform.position = newPosition;
        robotObject.transform.rotation = Quaternion.Euler(-robot_pitch, -robot_yaw, -robot_roll);
       // 一番上にあるUrdfLinkコンポーネントにIsBaseLinkを設定
        List<GameObject> childObjectsWithUrdfLink = GetChildObjectsWithComponent<UrdfLink>(robotObject);
        foreach (GameObject child in childObjectsWithUrdfLink)
        {
            UrdfLink link = child.GetComponent<UrdfLink>();
            link.IsBaseLink = true;
            
            ArticulationBody body = child.GetComponent<ArticulationBody>();
            body.immovable = robot_fixed;
            break;
        }

        // Parse URDF File
        XmlDocument xmlDoc = new XmlDocument();
        xmlDoc.Load(urdfFilePath);

        // Create PerfectOdometryPublisher
        GameObject targetObject1 = FindInChildrenByName(robotObject.transform, "base_link");
        Component PerfectOdometryScript = targetObject1.AddComponent<PerfectOdometryPublisher>();

        // Create PerfectMapPublisher
        Component PerfectMapScript = targetObject1.AddComponent<PerfectMapPublisher>();

        // Create JointStatePublisher & JointStateSubscriber
        JointStatePub jointStatePub = robotObject.AddComponent<JointStatePub>();
        JointStateSub jointStateSub = robotObject.AddComponent<JointStateSub>();
        List<GameObject> childObjectsWithArticulationBody = FindArticulationBodyObjectsInChildren(robotObject);
        List<ArticulationBody> articulationBodyList = new List<ArticulationBody>();
        List<string> jointNameList = new List<string>();
        foreach (GameObject child in childObjectsWithArticulationBody)
        {
            ArticulationBody body = child.GetComponent<ArticulationBody>();
            Debug.Log("Received joint type: " + body.jointType);
            if (System.Enum.IsDefined(typeof(ArticulationJointType), body.jointType))
            {
                if (body.jointType != ArticulationJointType.FixedJoint)
                {
                    UrdfJoint urdfJoint = child.GetComponent<UrdfJoint>();
                    articulationBodyList.Add(body);
                    jointNameList.Add(urdfJoint.jointName);
                    
                    var parameters = GetUnityDriveApiParameters(xmlDoc, urdfJoint.jointName);
                    ArticulationDrive drive = body.xDrive;
                    drive.stiffness = parameters["stiffness"];
                    drive.damping = parameters["damping"];
                    drive.forceLimit = parameters["force_limit"];
                    body.xDrive = drive;
                }
            }
        }

        jointStatePub.articulationBodies = articulationBodyList.ToArray();
        jointStatePub.jointName = jointNameList.ToArray();
        jointStatePub.jointLength = articulationBodyList.Count;
        XmlNode jointStateParam = xmlDoc.SelectSingleNode("//robot/ros2_control/hardware/param[@name='joint_states_topic']");
        if (jointStateParam != null)
        {
            jointStatePub.topicName = jointStateParam.InnerText;
        }

        jointStateSub.articulationBodies = articulationBodyList.ToArray();
        jointStateSub.jointName = jointNameList.ToArray();
        jointStateSub.jointLength = articulationBodyList.Count;
        XmlNode jointCommandParam = xmlDoc.SelectSingleNode("//robot/ros2_control/hardware/param[@name='joint_commands_topic']");
        if (jointCommandParam != null)
        {
            jointStateSub.topicName = jointCommandParam.InnerText;
        }

        // Physics Materialの生成
        // URDFのファイルパスからファイル名を取り除く
        string directoryPath = Path.GetDirectoryName(urdfFilePath);
        // "Assets"以前の文字列を取り除く
        int assetsIndex = directoryPath.IndexOf("Assets");
        if (assetsIndex >= 0)
        {
            directoryPath = directoryPath.Substring(assetsIndex);
        }
        // ディレクトリが存在するか確認し、存在しなければ作成する
        if (!Directory.Exists(directoryPath + "/PhysicsMaterials"))
        {
            Directory.CreateDirectory(directoryPath + "/PhysicsMaterials");
            Debug.Log("Directory created at: " + directoryPath + "/PhysicsMaterials");
        }
        // <robot>要素を取得
        XmlNode robotNode = xmlDoc.SelectSingleNode("/robot");
        if (robotNode != null)
        {
            // 全ての<physics_material>要素を取得
            XmlNodeList physicsMaterials = robotNode.SelectNodes("physics_material");
            foreach (XmlNode physicsMaterial in physicsMaterials)
            {
                PhysicsMaterial newMaterial = new PhysicsMaterial();
                XmlNode frictionNode = physicsMaterial.SelectSingleNode("friction");
                if (frictionNode != null)
                {
                    newMaterial.staticFriction = TryParseFloat(frictionNode.Attributes["static"]?.Value);
                    newMaterial.dynamicFriction = TryParseFloat(frictionNode.Attributes["dynamic"]?.Value);
                }

                string materialName = physicsMaterial.Attributes["name"]?.Value;
                string path = directoryPath + "/PhysicsMaterials/" + materialName + ".physicMaterial";

                AssetDatabase.CreateAsset(newMaterial, path);
                AssetDatabase.SaveAssets();
            }
        }


        if (robotNode != null)
        {
            XmlNodeList links = robotNode.SelectNodes("link");
            foreach (XmlNode link in links)
            {
                XmlNodeList unitySensors = link.SelectNodes("unity_sensor");

                if (unitySensors != null && unitySensors.Count > 0)
                {
                    Debug.Log("<unity_sensor> found for : " + link.Attributes["name"]?.Value);


                    string linkName = link.Attributes["name"]?.Value;

                    GameObject targetObject = FindInChildrenByName(robotObject.transform, linkName);
                    if (targetObject != null)
                    {

                        foreach (XmlNode unitySensor in unitySensors)
                        {

                            string type = unitySensor.Attributes["type"]?.Value;
                            if (!string.IsNullOrEmpty(type))
                            {   
                                if(type=="vlp16"){
                                   LoadVLP16(targetObject,unitySensor,linkName);
                                }
                                else if(type=="camera_RGB"){
                                    LoadCamRGB(targetObject,unitySensor,linkName);
                                }
                                else if(type=="camera_Depth"){
                                    LoadCamDepth(targetObject,unitySensor,linkName);
                                }
                                else if(type=="imu"){
                                    LoadIMU(targetObject,unitySensor,linkName);
                                }
                                else if(type=="gnss"){
                                    LoadIMU(targetObject,unitySensor,linkName);
                                }
                                else if(type=="laser_scan"){
                                    LoadLaserScan(targetObject,unitySensor,linkName);
                                }
                                else
                                {
                                    Debug.LogWarning("Sensor type error for " + linkName + " => "+type+" Type unknown");
                                }
                            }
                            else
                            {
                                Debug.LogWarning("Sensor type error for " + linkName + " => Type empty");
                            }
                        }
                    }
                    else
                    {
                        Debug.LogWarning("No GameObject found for " + linkName);
                    }
                }
            }
        }


        // Physics Materialの適用
        // <robot>要素を取得
        if (robotNode != null)
        {
            // 全ての<link>要素を取得
            XmlNodeList links = robotNode.SelectNodes("link");
            foreach (XmlNode link in links)
            {   
                XmlNode collisionNode = link.SelectSingleNode("collision");
                if (collisionNode != null)
                {
                    XmlNode physicsMaterial = collisionNode.SelectSingleNode("physics_material");
                    if (physicsMaterial != null)
                    {
                        string materialName = physicsMaterial.Attributes["name"]?.Value;
                        string linkName = link.Attributes["name"]?.Value;
                        GameObject targetObject = FindInChildrenByName(robotObject.transform, linkName);
                        if (targetObject != null)
                        {
                            Transform collisionTransform = targetObject.transform.Find("Collisions");
                            if (collisionTransform != null)
                            {
                                Transform unnamedCollision = collisionTransform.GetChild(0);
                                Transform targetCollision = unnamedCollision.GetChild(0);
                                if (targetCollision != null)
                                {
                                    Debug.Log(materialName + ": " + linkName);
                                    Collider meshCollider = targetCollision.gameObject.GetComponent<Collider>();
                                    if (meshCollider != null)
                                    {
                                        string path = directoryPath + "/PhysicsMaterials/" + materialName + ".physicMaterial";
                                        PhysicsMaterial loadedMaterial = AssetDatabase.LoadAssetAtPath<PhysicsMaterial>(path);
                                    
                                        meshCollider.material = loadedMaterial;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            if (EditorGUI.EndChangeCheck())
            {
                var prefabStage = PrefabStageUtility.GetCurrentPrefabStage();
                if (prefabStage != null)
                    EditorSceneManager.MarkSceneDirty(prefabStage.scene);
                var scene = SceneManager.GetActiveScene();
                EditorSceneManager.MarkSceneDirty(scene);
            }
        }
        
        UnityEngine.Object.DestroyImmediate(robotObject.GetComponent<Controller>());
    }

    private static void StopListener()
    {
        isRunning = false;

        // clientがnullでないことを確認してからCloseする
        if (client != null)
        {
            client.Close();
            client = null; // 次回呼び出し時に二重Closeを防ぐ
        }

        // listenerがnullでないことを確認してからStopする
        if (listener != null)
        {
            listener.Stop();
            listener = null; // 次回呼び出し時に二重Stopを防ぐ
        }
    }

    private static void OnApplicationQuit()
    {
        StopListener();
    }

    private static GameObject FindInChildrenByName(Transform parent, string name)
    {
        // 現在のオブジェクトが目的の名前かを確認
        if (parent.name == name)
        {
            return parent.gameObject;
        }

        // 子オブジェクトを再帰的にチェック
        foreach (Transform child in parent)
        {
            GameObject result = FindInChildrenByName(child, name);
            if (result != null)
            {
                return result;
            }
        }
        
        // 見つからなかった場合
        return null;
    }
    
    // 特定のコンポーネントを持つ子オブジェクトを取得するメソッド
    private static List<GameObject> GetChildObjectsWithComponent<T>(GameObject parent) where T : Component
    {
        List<GameObject> objectsWithComponent = new List<GameObject>();

        // 親オブジェクトのすべての子オブジェクトをループ
        foreach (Transform child in parent.transform)
        {
            // 子オブジェクトが指定されたコンポーネントを持っているか確認
            if (child.GetComponent<T>() != null)
            {
                objectsWithComponent.Add(child.gameObject); // リストに追加
            }
        }

        return objectsWithComponent;
    }

    // ArticulationBodyを持つGameObjectを探してリストとして返す
    public static List<GameObject> FindArticulationBodyObjectsInChildren(GameObject parent)
    {
        List<GameObject> articulationBodies = new List<GameObject>();
        SearchArticulationBodies(parent.transform, articulationBodies);
        return articulationBodies;
    }

    // 再帰的にArticulationBodyを持つ子オブジェクトを検索
    private static void SearchArticulationBodies(Transform parent, List<GameObject> articulationBodies)
    {
        // 現在のオブジェクトがArticulationBodyを持っている場合、リストに追加
        ArticulationBody articulationBody = parent.GetComponent<ArticulationBody>();
        if (articulationBody != null)
        {
            articulationBodies.Add(parent.gameObject);
        }

        // 子オブジェクトを再帰的にチェック
        foreach (Transform child in parent)
        {
            SearchArticulationBodies(child, articulationBodies);
        }
    }

    private static void SetProperty(Component component, string propertyName, string value)
    {
        if (component != null && !string.IsNullOrEmpty(value))
        {
            var property = component.GetType().GetProperty(propertyName);
            if (property != null)
            {
                // Convertir la valeur au bon type si nécessaire
                object convertedValue = Convert.ChangeType(value, property.PropertyType);
                property.SetValue(component, convertedValue);
            }
            else
            {
                Debug.LogWarning($"Propriété {propertyName} introuvable sur le script {component.GetType().Name}.");
            }
        }
    }

    public static Dictionary<string, float> GetUnityDriveApiParameters(XmlDocument xmlDoc, string targetJointName)
    {
        var parameters = new Dictionary<string, float>();

        // <robot>要素を取得
        XmlNode robotNode = xmlDoc.SelectSingleNode("/robot");
        if (robotNode != null)
        {
            // 全ての<joint>要素を取得
            XmlNodeList jointNodes = robotNode.SelectNodes("joint");

            foreach (XmlNode jointNode in jointNodes)
            {
                // 指定されたname属性のjointタグを探す
                if (jointNode.Attributes["name"]?.Value == targetJointName)
                {
                    // unity_drive_api内の各パラメータの取得
                    XmlNode unityDriveApiNode = jointNode.SelectSingleNode("unity_drive_api");
                    if (unityDriveApiNode != null)
                    {
                        // stiffness, damping, force_limitをfloat型に変換して追加
                        parameters["stiffness"] = TryParseFloat(unityDriveApiNode.Attributes["stiffness"]?.Value);
                        parameters["damping"] = TryParseFloat(unityDriveApiNode.Attributes["damping"]?.Value);
                        parameters["force_limit"] = TryParseFloat(unityDriveApiNode.Attributes["force_limit"]?.Value);
                    }
                    else
                    {
                        Console.WriteLine("unity_drive_api element not found.");
                        parameters["stiffness"] = 0.0F;
                        parameters["damping"] = 0.0F;
                        parameters["force_limit"] = 0.0F;
                    }
                    return parameters; // 見つけたら戻り値を返す
                }
            }

            // 指定されたnameが見つからなかった場合
            Console.WriteLine("Joint with the specified name not found.");
        }
        else
        {
            Console.WriteLine("Robot element not found.");
        }

        parameters["stiffness"] = 0.0F;
        parameters["damping"] = 0.0F;
        parameters["force_limit"] = 0.0F;

        return parameters;
    }

    // 文字列をfloatに変換するためのヘルパーメソッド
    private static float TryParseFloat(string value)
    {
        return float.TryParse(value, out float result) ? result : 0f;
    }

    public static void LoadVLP16(GameObject targetObj,XmlNode unitySensor, String linkName){
        Component lidarSensorScript = targetObj.AddComponent<RaycastLiDARSensor>();
        Component lidarPublishScript = targetObj.AddComponent<RaycastLiDARPointCloud2MsgPublisher>();
        
        SerializedObject lidarSensorScriptserializedObject = new SerializedObject(lidarSensorScript);
        SerializedObject lidarPublishScriptserializedObject = new SerializedObject(lidarPublishScript);
        
        SerializedProperty Sensor_freq = lidarSensorScriptserializedObject.FindProperty("_frequency");
        SerializedProperty Scan_Pattern = lidarSensorScriptserializedObject.FindProperty("_scanPattern");
        SerializedProperty N_points = lidarSensorScriptserializedObject.FindProperty("_pointsNumPerScan");
        SerializedProperty Min_rng = lidarSensorScriptserializedObject.FindProperty("_minRange");
        SerializedProperty Max_rng = lidarSensorScriptserializedObject.FindProperty("_maxRange");
        SerializedProperty Gaus_noise = lidarSensorScriptserializedObject.FindProperty("_gaussianNoiseSigma");
        SerializedProperty Max_I = lidarSensorScriptserializedObject.FindProperty("_maxIntensity");

        SerializedProperty Topic_name = lidarPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq = lidarPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty = lidarPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty = serializerProperty.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty = headerProperty.FindPropertyRelative("_frame_id");

        
        float.TryParse(unitySensor.Attributes["sensor_frequency"]?.Value, out float sensorFrequency);
        int.TryParse(unitySensor.Attributes["points_num_per_scan"]?.Value, out int pointsNumPerScan);
        float.TryParse(unitySensor.Attributes["min_range"]?.Value, out float minRange);
        float.TryParse(unitySensor.Attributes["max_range"]?.Value, out float maxRange);
        float.TryParse(unitySensor.Attributes["gaussian_noise_sigma"]?.Value, out float gaussianNoiseSigma);
        float.TryParse(unitySensor.Attributes["max_intensity"]?.Value, out float maxIntensity);

        float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishingFrequency);
        string topicName = unitySensor.Attributes["topic_name"]?.Value;

        Sensor_freq.floatValue = sensorFrequency;
        Scan_Pattern.objectReferenceValue=AssetDatabase.LoadAssetAtPath<ScanPattern>("Assets/Resources/VLP-16.asset");
        N_points.intValue=pointsNumPerScan;
        Min_rng.floatValue=minRange;
        Max_rng.floatValue=maxRange;
        Gaus_noise.floatValue=gaussianNoiseSigma;
        Max_I.floatValue=maxIntensity;

        Publish_freq.floatValue=publishingFrequency;
        Topic_name.stringValue=topicName;
        frameIDProperty.stringValue = "/" + linkName;

        lidarSensorScriptserializedObject.ApplyModifiedProperties();
        lidarPublishScriptserializedObject.ApplyModifiedProperties();

    }

    public static void LoadCamRGB(GameObject targetObj,XmlNode unitySensor, String linkName){
        Component RGBCamSensorScript = targetObj.AddComponent<RGBCameraSensor>();
        Component CameraImageMsgPublishScript = targetObj.AddComponent<CameraImageMsgPublisher>();
        Component CameraInfoMsgPublishScript = targetObj.AddComponent<CameraInfoMsgPublisher>();
        
        SerializedObject RGBCamSensorScripttserializedObject = new SerializedObject(RGBCamSensorScript);
        SerializedObject CameraImageMsgPublishScriptserializedObject = new SerializedObject(CameraImageMsgPublishScript);
        SerializedObject CameraInfoMsgPublishScriptserializedObject = new SerializedObject(CameraInfoMsgPublishScript);
        
        SerializedProperty Sensor_freq = RGBCamSensorScripttserializedObject.FindProperty("_frequency");
        SerializedProperty Min_rng = RGBCamSensorScripttserializedObject.FindProperty("_minRange");
        SerializedProperty Max_rng = RGBCamSensorScripttserializedObject.FindProperty("_maxRange");
        SerializedProperty fov = RGBCamSensorScripttserializedObject.FindProperty("_fov");
        SerializedProperty Resolution = RGBCamSensorScripttserializedObject.FindProperty("_resolution");
        SerializedProperty Res_x = Resolution.FindPropertyRelative("x");
        SerializedProperty Res_y = Resolution.FindPropertyRelative("y");

        SerializedProperty Topic_name_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty_Im = serializerProperty_Im.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty_Im = headerProperty_Im.FindPropertyRelative("_frame_id");
        SerializedProperty qualityProperty = serializerProperty_Im.FindPropertyRelative("quality");

        SerializedProperty Topic_name_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty_Inf = serializerProperty_Inf.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty_Inf = headerProperty_Inf.FindPropertyRelative("_frame_id");

        
        float.TryParse(unitySensor.Attributes["sensor_frequency"]?.Value, out float sensorFrequency);
        int.TryParse(unitySensor.Attributes["res_x"]?.Value, out int Resolutionx);
        int.TryParse(unitySensor.Attributes["res_y"]?.Value, out int Resolutiony);
        float.TryParse(unitySensor.Attributes["min_range"]?.Value, out float minRange);
        float.TryParse(unitySensor.Attributes["max_range"]?.Value, out float maxRange);
        float.TryParse(unitySensor.Attributes["fov"]?.Value, out float FoV);

        float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishingFrequency);
        int.TryParse(unitySensor.Attributes["quality"]?.Value, out int Im_quality);
        string Im_topicName = unitySensor.Attributes["image_topic_name"]?.Value;
        string Inf_topicName = unitySensor.Attributes["info_topic_name"]?.Value;

        Sensor_freq.floatValue = sensorFrequency;
        Min_rng.floatValue=minRange;
        Max_rng.floatValue=maxRange;
        Res_x.intValue=Resolutionx;
        Res_y.intValue=Resolutiony;
        fov.floatValue=FoV;

        qualityProperty.intValue=Im_quality;
        Publish_freq_Im.floatValue=publishingFrequency;
        Topic_name_Im.stringValue=Im_topicName;
        frameIDProperty_Im.stringValue=linkName;
        
        Publish_freq_Inf.floatValue=publishingFrequency;
        Topic_name_Inf.stringValue=Inf_topicName;
        frameIDProperty_Inf.stringValue=linkName;

        RGBCamSensorScripttserializedObject.ApplyModifiedProperties();
        CameraImageMsgPublishScriptserializedObject.ApplyModifiedProperties();
        CameraInfoMsgPublishScriptserializedObject.ApplyModifiedProperties();
    }

    public static void LoadCamDepth(GameObject targetObj,XmlNode unitySensor, String linkName){
        Component DepthCamSensorScript = targetObj.AddComponent<DepthCameraSensor>();
        Component CameraImageMsgPublishScript = targetObj.AddComponent<CameraImageMsgPublisher>();
        Component CameraInfoMsgPublishScript = targetObj.AddComponent<CameraInfoMsgPublisher>();
        Component DepthCameraPointCloud2MsgPublishScript = targetObj.AddComponent<DepthCameraPointCloud2MsgPublisher>();
        
        SerializedObject DepthCamSensorScripttserializedObject = new SerializedObject(DepthCamSensorScript);
        SerializedObject CameraImageMsgPublishScriptserializedObject = new SerializedObject(CameraImageMsgPublishScript);
        SerializedObject CameraInfoMsgPublishScriptserializedObject = new SerializedObject(CameraInfoMsgPublishScript);
        SerializedObject DepthCameraPointCloud2MsgPublishScriptserializedObject = new SerializedObject(DepthCameraPointCloud2MsgPublishScript);
        
        SerializedProperty Sensor_freq = DepthCamSensorScripttserializedObject.FindProperty("_frequency");
        SerializedProperty Min_rng = DepthCamSensorScripttserializedObject.FindProperty("_minRange");
        SerializedProperty Max_rng = DepthCamSensorScripttserializedObject.FindProperty("_maxRange");
        SerializedProperty fov = DepthCamSensorScripttserializedObject.FindProperty("_fov");
        SerializedProperty Resolution = DepthCamSensorScripttserializedObject.FindProperty("_resolution");
        SerializedProperty Res_x = Resolution.FindPropertyRelative("x");
        SerializedProperty Res_y = Resolution.FindPropertyRelative("y");

        SerializedProperty Topic_name_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty_Im = CameraImageMsgPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty_Im = serializerProperty_Im.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty_Im = headerProperty_Im.FindPropertyRelative("_frame_id");
        SerializedProperty qualityProperty = serializerProperty_Im.FindPropertyRelative("quality");

        SerializedProperty Topic_name_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty_Inf = CameraInfoMsgPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty_Inf = serializerProperty_Inf.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty_Inf = headerProperty_Inf.FindPropertyRelative("_frame_id");

        SerializedProperty Topic_name_PC = DepthCameraPointCloud2MsgPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq_PC = DepthCameraPointCloud2MsgPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty_PC = DepthCameraPointCloud2MsgPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty_PC = serializerProperty_PC.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty_PC = headerProperty_PC.FindPropertyRelative("_frame_id");


        
        float.TryParse(unitySensor.Attributes["sensor_frequency"]?.Value, out float sensorFrequency);
        int.TryParse(unitySensor.Attributes["res_x"]?.Value, out int Resolutionx);
        int.TryParse(unitySensor.Attributes["res_y"]?.Value, out int Resolutiony);
        float.TryParse(unitySensor.Attributes["min_range"]?.Value, out float minRange);
        float.TryParse(unitySensor.Attributes["max_range"]?.Value, out float maxRange);
        float.TryParse(unitySensor.Attributes["fov"]?.Value, out float FoV);

        float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishingFrequency);
        int.TryParse(unitySensor.Attributes["quality"]?.Value, out int Im_quality);
        string Im_topicName = unitySensor.Attributes["image_topic_name"]?.Value;
        string Inf_topicName = unitySensor.Attributes["info_topic_name"]?.Value;
        string PC_topicName = unitySensor.Attributes["PC_topic_name"]?.Value;

        Sensor_freq.floatValue = sensorFrequency;
        Min_rng.floatValue=minRange;
        Max_rng.floatValue=maxRange;
        Res_x.intValue=Resolutionx;
        Res_y.intValue=Resolutiony;
        fov.floatValue=FoV;

        qualityProperty.intValue=Im_quality;
        Publish_freq_Im.floatValue=publishingFrequency;
        Topic_name_Im.stringValue=Im_topicName;
        frameIDProperty_Im.stringValue=linkName;
        
        Publish_freq_Inf.floatValue=publishingFrequency;
        Topic_name_Inf.stringValue=Inf_topicName;
        frameIDProperty_Inf.stringValue=linkName;

        Publish_freq_PC.floatValue=publishingFrequency;
        Topic_name_PC.stringValue=PC_topicName;
        frameIDProperty_PC.stringValue=linkName;

        DepthCamSensorScripttserializedObject.ApplyModifiedProperties();
        CameraImageMsgPublishScriptserializedObject.ApplyModifiedProperties();
        CameraInfoMsgPublishScriptserializedObject.ApplyModifiedProperties();
        DepthCameraPointCloud2MsgPublishScriptserializedObject.ApplyModifiedProperties();
    }

    public static void LoadIMU(GameObject targetObj,XmlNode unitySensor, String linkName){
        Component IMUSensorScript = targetObj.AddComponent<IMUSensor>();
        Component IMUPublishScript = targetObj.AddComponent<IMUMsgPublisher>();
        
        SerializedObject IMUSensorScriptserializedObject = new SerializedObject(IMUSensorScript);
        SerializedObject IMUPublishScriptserializedObject = new SerializedObject(IMUPublishScript);
        
        SerializedProperty Sensor_freq = IMUSensorScriptserializedObject.FindProperty("_frequency");

        SerializedProperty Topic_name = IMUPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq = IMUPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty = IMUPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty = serializerProperty.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty = headerProperty.FindPropertyRelative("_frame_id");

        
        float.TryParse(unitySensor.Attributes["sensor_frequency"]?.Value, out float sensorFrequency);

        float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishingFrequency);
        string topicName = unitySensor.Attributes["topic_name"]?.Value;

        Sensor_freq.floatValue = sensorFrequency;

        Publish_freq.floatValue=publishingFrequency;
        Topic_name.stringValue=topicName;
        frameIDProperty.stringValue = "/" + linkName;

        IMUSensorScriptserializedObject.ApplyModifiedProperties();
        IMUPublishScriptserializedObject.ApplyModifiedProperties();

    }

    public static void LoadGNSS(GameObject targetObj,XmlNode unitySensor, String linkName){
        Component GNSSSensorScript = targetObj.AddComponent<GNSSSensor>();
        Component NavSatFixPublishScript = targetObj.AddComponent<NavSatFixMsgPublisher>();
        
        SerializedObject GNSSSensorScriptserializedObject = new SerializedObject(GNSSSensorScript);
        SerializedObject NavSatFixPublishScriptserializedObject = new SerializedObject(NavSatFixPublishScript);
        
        SerializedProperty Sensor_freq = GNSSSensorScriptserializedObject.FindProperty("_frequency");

        SerializedProperty Topic_name = NavSatFixPublishScriptserializedObject.FindProperty("_topicName");
        SerializedProperty Publish_freq = NavSatFixPublishScriptserializedObject.FindProperty("_frequency");
        SerializedProperty serializerProperty = NavSatFixPublishScriptserializedObject.FindProperty("_serializer");
        SerializedProperty headerProperty = serializerProperty.FindPropertyRelative("_header");
        SerializedProperty frameIDProperty = headerProperty.FindPropertyRelative("_frame_id");

        
        float.TryParse(unitySensor.Attributes["sensor_frequency"]?.Value, out float sensorFrequency);

        float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishingFrequency);
        string topicName = unitySensor.Attributes["topic_name"]?.Value;

        Sensor_freq.floatValue = sensorFrequency;

        Publish_freq.floatValue=publishingFrequency;
        Topic_name.stringValue=topicName;
        frameIDProperty.stringValue = "/" + linkName;

        GNSSSensorScriptserializedObject.ApplyModifiedProperties();
        NavSatFixPublishScriptserializedObject.ApplyModifiedProperties();

    }

    public static void LoadLaserScan(GameObject targetObj,XmlNode unitySensor, String linkName){
        LaserScanPublishing laserScanPublisher = targetObj.AddComponent<LaserScanPublishing>();

        if (laserScanPublisher != null)
        {
            int.TryParse(unitySensor.Attributes["number_ray"]?.Value, out int number_rays);
            float.TryParse(unitySensor.Attributes["scan_range"]?.Value, out float scan_range);
            float.TryParse(unitySensor.Attributes["min_range"]?.Value, out float min_range);
            float.TryParse(unitySensor.Attributes["scan_angle"]?.Value, out float scan_angle);
            float.TryParse(unitySensor.Attributes["publishing_frequency"]?.Value, out float publishing_frequency);

            string topic_name = unitySensor.Attributes["topic_name"]?.Value;
            

            laserScanPublisher.numberOfRays = number_rays;       
            laserScanPublisher.scanRange = scan_range;           
            laserScanPublisher.minRange = min_range;           
            laserScanPublisher.scanAngle = scan_angle;    
            laserScanPublisher.frame_ID = linkName;
            laserScanPublisher.topicName  =  topic_name;
            laserScanPublisher.publishingFrequency =  publishing_frequency;
            laserScanPublisher.obstacleLayer = ~0;

        }else
        {
            Debug.LogError("No script found");
        }
    }

}

