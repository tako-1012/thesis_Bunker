using UnityEditor;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.Core;
using RosMessageTypes.Rosgraph;
using RosMessageTypes.BuiltinInterfaces;

[ExecuteAlways]
public class PublishClock : MonoBehaviour
{
    private ROSConnection ros; // ROS connection
    public string topicName = "/clock"; // Topic name
    public float publishRate = 100.0f; // Publish rate in Hz (default: 100 Hz)
    private float publishTimer = 0.0f; // Internal timer for publish rate control
    double now;

    void Start()
    {
        // Initialize the ROS connection
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<ClockMsg>(topicName);

    }

    void Update()
    {
        if (Application.isPlaying)
        {
            // Accumulate delta time
            publishTimer += Time.deltaTime;

            // Publish only if the timer reaches the interval (1 / publishRate)
            if (publishTimer >= 1.0f / publishRate)
            {
                PublishClockMessage();
                publishTimer = 0.0f; // Reset the timer
            }
        }
    }

    void PublishClockMessage()
    {
        // Create a new Clock message
        ClockMsg clockMsg = new ClockMsg();
        
        // Calculer l'heure actuelle (avec l'offset global)
        now = Unity.Robotics.Core.Clock.Now;
        
        clockMsg.clock = new TimeMsg
        {
            sec = (int)now, // Partie entière de l'heure actuelle
            nanosec = (uint)((now - Mathf.Floor((float)now)) * 1e9) // Partie décimale convertie en nanosecondes
        };

        // Publish the message
        ros.Publish(topicName, clockMsg);
        
    }
}
